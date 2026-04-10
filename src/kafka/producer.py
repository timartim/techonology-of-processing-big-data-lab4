import json

from aiokafka import AIOKafkaProducer


class KafkaPredictionProducer:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self.topic = topic
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            acks="all",
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish_prediction(self, prediction) -> None:
        payload = json.dumps(prediction.model_dump(mode="json")).encode("utf-8")
        await self._producer.send_and_wait(self.topic, payload)