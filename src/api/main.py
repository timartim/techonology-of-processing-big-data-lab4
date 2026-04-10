import os
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI
from redis.asyncio import from_url

from src.api.routes import router
from src.api.repositories.prediction_repository import PredictionRepository
from src.api.services.prediction_service import PredictionService
from src.common.vault_client import read_kv_secret_from_vault_with_retry
from src.kafka.producer import KafkaPredictionProducer
from src.models.CatVDogModel import CatVDogModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_cfg = read_kv_secret_from_vault_with_retry(
        secret_path=os.getenv("VAULT_REDIS_SECRET_PATH", "catdog/redis")
    )
    kafka_cfg = read_kv_secret_from_vault_with_retry(
        secret_path=os.getenv("VAULT_KAFKA_SECRET_PATH", "catdog/kafka")
    )

    redis_url = (
        f"redis://{quote(redis_cfg['username'])}:{quote(redis_cfg['password'])}"
        f"@{redis_cfg['host']}:{redis_cfg['port']}/{redis_cfg['db']}"
    )

    redis = from_url(redis_url, decode_responses=True)
    await redis.ping()

    producer = KafkaPredictionProducer(
        bootstrap_servers=kafka_cfg["bootstrapServers"],
        topic=kafka_cfg["topicPredictions"],
    )
    await producer.start()

    model_version = os.getenv("MODEL_VERSION", "1.0.0")
    device = os.getenv("MODEL_DEVICE", "cpu")
    classifier_key = os.getenv("CLASSIFIER_KEY", "LOG_REG")

    model_service = CatVDogModel(config_path="config.ini", show_log=True)
    model_service.set_device(device)
    model_service.load_classifier(classifier_key)

    repository = PredictionRepository(redis)

    prediction_service = PredictionService(
        ml_service=model_service,
        repository=repository,
        model_version=model_version,
        prediction_repository=repository,
        event_producer=producer,
    )

    app.state.redis = redis
    app.state.prediction_service = prediction_service

    try:
        yield
    finally:
        await producer.stop()
        await redis.aclose()


app = FastAPI(
    title="Dog vs Cat API",
    lifespan=lifespan,
)

app.include_router(router)