from datetime import datetime

from redis.asyncio import Redis
from src.api.schemas import PredictionRecord


class PredictionRepository:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_consumed_by_id(self, prediction_id: str) -> PredictionRecord | None:
        key = f"prediction-consumed:{prediction_id}"
        item = await self.redis.hgetall(key)

        if not item:
            return None

        return PredictionRecord(
            predictionId=item["predictionId"],
            fileName=item["fileName"],
            createdAt=datetime.fromisoformat(item["createdAt"]),
            dogProbability=float(item["dogProbability"]),
            predictedLabel=item["predictedLabel"],
            modelVersion=item["modelVersion"],
        )

    async def get_last_consumed(self, limit: int) -> list[PredictionRecord]:
        raw_ids = await self.redis.zrevrange("predictions:consumed:by_time", 0, limit - 1)

        if not raw_ids:
            return []

        pipe = self.redis.pipeline()
        for prediction_id in raw_ids:
            pipe.hgetall(f"prediction-consumed:{prediction_id}")

        raw_predictions = await pipe.execute()

        result: list[PredictionRecord] = []

        for item in raw_predictions:
            if not item:
                continue

            result.append(
                PredictionRecord(
                    predictionId=item["predictionId"],
                    fileName=item["fileName"],
                    createdAt=datetime.fromisoformat(item["createdAt"]),
                    dogProbability=float(item["dogProbability"]),
                    predictedLabel=item["predictedLabel"],
                    modelVersion=item["modelVersion"],
                )
            )

        return result