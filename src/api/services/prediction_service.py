from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from src.api.schemas import PredictionRecord
from src.api.repositories.prediction_repository import PredictionRepository


class PredictionService:
    def __init__(
        self,
        ml_service,
        repository: PredictionRepository,
        model_version: str,
        prediction_repository
    ) -> None:
        self.ml_service = ml_service
        self.repository = repository
        self.model_version = model_version
        self.prediction_repository = prediction_repository
    async def predict_and_save(self, file_bytes: bytes, file_name: str) -> PredictionRecord:
        try:
            img = Image.open(BytesIO(file_bytes)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise HTTPException(status_code=400, detail="Invalid image file") from exc

        clf = self.ml_service.classifier
        if clf is None:
            raise HTTPException(status_code=500, detail="Classifier is not loaded")

        if not hasattr(clf, "predict_proba"):
            raise HTTPException(
                status_code=500,
                detail="Classifier does not support predict_proba",
            )

        emb = self.ml_service.embed_pil(img).reshape(1, -1)
        proba = clf.predict_proba(emb)

        dog_class_index = 1
        dog_prob = float(proba[0, dog_class_index])
        predicted_label = "dog" if dog_prob >= 0.5 else "cat"

        prediction = PredictionRecord(
            predictionId=str(uuid4()),
            fileName=file_name,
            createdAt=datetime.now(timezone.utc),
            dogProbability=dog_prob,
            predictedLabel=predicted_label,
            modelVersion=self.model_version,
        )

        await self.repository.save(prediction)
        return prediction

    async def get_last_predictions(self, limit: int) -> list[PredictionRecord]:
        return await self.prediction_repository.get_last(limit)