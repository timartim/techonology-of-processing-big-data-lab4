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

        pipe = self.redis.pipeline()
        for prediction_id in raw_ids:
            pipe.hgetall(f"prediction:{prediction_id}")

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