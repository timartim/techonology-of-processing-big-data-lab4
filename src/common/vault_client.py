import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def read_kv_secret_from_vault(secret_path: str) -> dict:
    vault_addr = os.environ["VAULT_ADDR"].rstrip("/")
    mount = os.getenv("VAULT_KV_MOUNT", "app")
    token = login_to_vault()

    response = http_get_json(
        f"{vault_addr}/v1/{mount}/data/{secret_path}",
        headers={"X-Vault-Token": token},
    )

    try:
        return response["data"]["data"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected Vault KV response: {response}") from exc


def read_kv_secret_from_vault_with_retry(secret_path: str, retries: int = 20, delay: float = 2.0) -> dict:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            return read_kv_secret_from_vault(secret_path)
        except (HTTPError, URLError, KeyError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(f"Vault secret {secret_path} is not ready after {retries} attempts") from last_error