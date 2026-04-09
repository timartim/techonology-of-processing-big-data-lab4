from datetime import datetime

from redis.asyncio import Redis
from src.api.schemas import PredictionRecord


class PredictionRepository:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def save(self, prediction: PredictionRecord) -> None:
        key = f"prediction:{prediction.predictionId}"

        await self.redis.hset(
            key,
            mapping={
                "predictionId": prediction.predictionId,
                "fileName": prediction.fileName,
                "createdAt": prediction.createdAt.isoformat(),
                "dogProbability": str(prediction.dogProbability),
                "predictedLabel": prediction.predictedLabel,
                "modelVersion": prediction.modelVersion,
            },
        )

        await self.redis.zadd(
            "predictions:by_time",
            {prediction.predictionId: prediction.createdAt.timestamp()},
        )

    async def get_last(self, limit: int) -> list[PredictionRecord]:
        raw_ids = await self.redis.zrevrange("predictions:by_time", 0, limit - 1)

        if not raw_ids:
            return []

        prediction_ids = [
            item.decode("utf-8") if isinstance(item, bytes) else item
            for item in raw_ids
        ]

        pipe = self.redis.pipeline()
        for prediction_id in prediction_ids:
            pipe.hgetall(f"prediction:{prediction_id}")

        raw_predictions = await pipe.execute()

        result: list[PredictionRecord] = []

        for item in raw_predictions:
            if not item:
                continue

            normalized = {
                (k.decode("utf-8") if isinstance(k, bytes) else k):
                    (v.decode("utf-8") if isinstance(v, bytes) else v)
                for k, v in item.items()
            }

            result.append(
                PredictionRecord(
                    predictionId=normalized["predictionId"],
                    fileName=normalized["fileName"],
                    createdAt=datetime.fromisoformat(normalized["createdAt"]),
                    dogProbability=float(normalized["dogProbability"]),
                    predictedLabel=normalized["predictedLabel"],
                    modelVersion=normalized["modelVersion"],
                )
            )

        return result