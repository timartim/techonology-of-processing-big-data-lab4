from datetime import datetime
from pydantic import BaseModel


class PredictResponse(BaseModel):
    predictionId: str
    fileName: str
    createdAt: datetime
    dogProbability: float
    predictedLabel: str
    modelVersion: str


class PredictionRecord(BaseModel):
    predictionId: str
    fileName: str
    createdAt: datetime
    dogProbability: float
    predictedLabel: str
    modelVersion: str