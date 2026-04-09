import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import FastAPI
from redis.asyncio import from_url
import time
from urllib.error import HTTPError, URLError
from src.api.routes import router
from src.api.repositories.prediction_repository import PredictionRepository
from src.api.services.prediction_service import PredictionService
from src.models.CatVDogModel import CatVDogModel


def read_file_env(name: str) -> str:
    path = os.getenv(name)
    if not path:
        raise RuntimeError(f"Missing env: {name}")

    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"Empty file for env: {name}")

    return value


def http_post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url: str, headers: dict | None = None) -> dict:
    req = Request(url, method="GET")

    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login_to_vault() -> str:
    vault_addr = os.environ["VAULT_ADDR"].rstrip("/")
    role_id = read_file_env("VAULT_ROLE_ID_FILE")
    secret_id = read_file_env("VAULT_SECRET_ID_FILE")

    response = http_post_json(
        f"{vault_addr}/v1/auth/approle/login",
        {
            "role_id": role_id,
            "secret_id": secret_id,
        },
    )

    try:
        return response["auth"]["client_token"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected Vault login response: {response}") from exc


def read_redis_config_from_vault() -> dict:
    vault_addr = os.environ["VAULT_ADDR"].rstrip("/")
    mount = os.getenv("VAULT_KV_MOUNT", "app")
    secret_path = os.getenv("VAULT_SECRET_PATH", "catdog/redis")

    token = login_to_vault()

    response = http_get_json(
        f"{vault_addr}/v1/{mount}/data/{secret_path}",
        headers={"X-Vault-Token": token},
    )

    try:
        return response["data"]["data"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected Vault KV response: {response}") from exc

def read_redis_config_from_vault_with_retry(retries: int = 20, delay: float = 2.0) -> dict:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            return read_redis_config_from_vault()
        except (HTTPError, URLError, KeyError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(f"Vault is not ready after {retries} attempts") from last_error

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_cfg = read_redis_config_from_vault_with_retry()

    redis_host = redis_cfg["host"]
    redis_port = redis_cfg["port"]
    redis_db = redis_cfg["db"]
    redis_username = redis_cfg["username"]
    redis_password = redis_cfg["password"]

    model_version = os.getenv("MODEL_VERSION", "1.0.0")
    device = os.getenv("MODEL_DEVICE", "cpu")
    classifier_key = os.getenv("CLASSIFIER_KEY", "LOG_REG")

    redis_url = (
        f"redis://{quote(redis_username)}:{quote(redis_password)}"
        f"@{redis_host}:{redis_port}/{redis_db}"
    )

    redis = from_url(redis_url, decode_responses=True)
    await redis.ping()

    model_service = CatVDogModel(config_path="config.ini", show_log=True)
    model_service.set_device(device)
    model_service.load_classifier(classifier_key)

    repository = PredictionRepository(redis)

    prediction_service = PredictionService(
        ml_service=model_service,
        repository=repository,
        model_version=model_version,
        prediction_repository=repository,
    )

    app.state.redis = redis
    app.state.prediction_service = prediction_service

    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(
    title="Dog vs Cat API",
    lifespan=lifespan,
)

app.include_router(router)