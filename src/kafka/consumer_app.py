import asyncio
import json
from datetime import datetime
from urllib.parse import quote

from aiokafka import AIOKafkaConsumer
from redis.asyncio import from_url

from src.common.vault_client import read_kv_secret_from_vault_with_retry


class PredictionKafkaConsumer:
    def __init__(self, redis, consumer: AIOKafkaConsumer) -> None:
        self.redis = redis
        self.consumer = consumer

    async def save_consumed_event(self, event: dict) -> None:
        key = f"prediction-consumed:{event['predictionId']}"

        await self.redis.hset(
            key,
            mapping={
                "predictionId": event["predictionId"],
                "fileName": event["fileName"],
                "createdAt": event["createdAt"],
                "dogProbability": str(event["dogProbability"]),
                "predictedLabel": event["predictedLabel"],
                "modelVersion": event["modelVersion"],
            },
        )

        created_at_ts = datetime.fromisoformat(event["createdAt"]).timestamp()
        await self.redis.zadd(
            "predictions:consumed:by_time",
            {event["predictionId"]: created_at_ts},
        )

    async def start(self) -> None:
        await self.consumer.start()

    async def stop(self) -> None:
        await self.consumer.stop()
        await self.redis.aclose()

    async def run(self) -> None:
        await self.start()

        try:
            async for msg in self.consumer:
                event = json.loads(msg.value.decode("utf-8"))
                await self.save_consumed_event(event)
                print(f"Consumed prediction event: {event['predictionId']}")
        finally:
            await self.stop()


async def create_prediction_consumer() -> PredictionKafkaConsumer:
    redis_cfg = read_kv_secret_from_vault_with_retry(secret_path="catdog/redis")
    kafka_cfg = read_kv_secret_from_vault_with_retry(secret_path="catdog/kafka")

    redis_url = (
        f"redis://{quote(redis_cfg['username'])}:{quote(redis_cfg['password'])}"
        f"@{redis_cfg['host']}:{redis_cfg['port']}/{redis_cfg['db']}"
    )

    redis = from_url(redis_url, decode_responses=True)
    await redis.ping()

    kafka_consumer = AIOKafkaConsumer(
        kafka_cfg["topicPredictions"],
        bootstrap_servers=kafka_cfg["bootstrapServers"],
        group_id=kafka_cfg["consumerGroup"],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    return PredictionKafkaConsumer(
        redis=redis,
        consumer=kafka_consumer,
    )


async def main() -> None:
    consumer = await create_prediction_consumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())