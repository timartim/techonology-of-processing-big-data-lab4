# Cat V Dogs

This repository contains a simple **Machine Learning Engineering pipeline** for binary image classification (**cats vs dogs**).  
The system includes model training, inference API, experiment tracking, Docker deployment, and CI/CD pipelines.

---

# Project Overview

The model classifies images into two classes:

- `cat`
- `dog`

Architecture:

```text
Image
   ↓
ShuffleNet V2 (feature extractor)
   ↓
Embedding vector
   ↓
Logistic Regression
   ↓
Probability / class prediction
```

Key components:

- Feature extractor: **ShuffleNet V2 x0.5 (pretrained)**
- Classifier: **Logistic Regression**
- API: **FastAPI**
- Containerization: **Docker + Docker Compose**
- CI/CD: **GitHub Actions**
- Data versioning: **DVC**

---

# Installation

Clone repository:

```bash
git clone https://github.com/timartim/techonology-of-processing-big-data.git
cd techonology-of-processing-big-data
```
---

# Docker Compose
before you start, you need to create directory and write down your secrets ther secrets. 
```bash
mkdir -p secrets

printf "%s" "kafka:9092" > secrets/kafka_bootstrap_servers.txt
printf "%s" "catdog-consumer" > secrets/kafka_consumer_group.txt
printf "%s" "1" > secrets/kafka_node_id.txt
printf "%s" "9092" > secrets/kafka_port.txt
printf "%s" "predictions.created" > secrets/kafka_topic_predictions.txt

printf "%s" "0" > secrets/redis_db.txt
printf "%s" "redis" > secrets/redis_host.txt
printf "%s" "strong_password" > secrets/redis_password.txt
printf "%s" "6379" > secrets/redis_port.txt
printf "%s" "model_writer" > secrets/redis_username.txt

cat > secrets/redis_users.acl <<'EOF'
user default off
user model_writer on >strong_password ~prediction:* ~predictions:* ~prediction-consumed:* ~predictions:consumed:* +ping +hset +hgetall +zadd +zrevrange +multi +exec +select +client
EOF

chmod 644 secrets/*
```

To run the service you need to complete next steps:

Firstly build docker image 
```bash
docker compose build --progress=plain
```
Start vault, redis and kafka
```bash
docker compose up kafka redis vault
```

Then make bootstrap script executable
```bash
chmod +x scripts/bootstrap_vault.sh
```
Run bootstrap script
```bash
./scripts/bootstrap_vault.sh
```

Ensure that kafka topic is created (optional):
```bash
docker compose exec -T kafka sh -lc '
KAFKA_PORT="$(cat /run/secrets/kafka_port)"
KAFKA_TOPIC_PREDICTIONS="$(cat /run/secrets/kafka_topic_predictions)"

/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server "localhost:${KAFKA_PORT}" \
  --create \
  --if-not-exists \
  --topic "${KAFKA_TOPIC_PREDICTIONS}" \
  --partitions 1 \
  --replication-factor 1
'
```


Then up the web and consumer service:
```bash
docker compose up web consumer
```


To stop service:

```bash
docker compose down
```

API will be available at:

```text
http://localhost:8001
```

Swagger:

```text
http://localhost:8001/docs
```

---

# CI/CD

CI/CD pipelines are implemented using **GitHub Actions**.

Workflows:

```text
.github/workflows/
    ci.yml
    cd.yml
```

### CI pipeline

Runs on commits and pull requests:

- builds Docker image
- runs tests
- evaluates model metrics
- validates application startup

### CD pipeline

Runs after merge into `main`:

- builds and publishes Docker image
- pulls the latest image
- starts API container
- runs functional API checks

Example functional test:

```bash
curl -X POST -F "file=@dog.jpg" http://localhost:8001/predict
```

Validation rule:

```text
dog image  -> probability > 0.5
cat image  -> probability < 0.5
```

---

# DVC

Data versioning is implemented with **DVC** and remote storage.

Initialize DVC:

```bash
dvc init
```

Pull dataset:

```bash
dvc pull
```

Push dataset:

```bash
dvc push
```

---

# Model Metrics

Example metrics on validation set:

| Metric    | Score |
|-----------|-------|
| Precision | 0.96  |
| Recall    | 0.97  |
| F1        | 0.96  |
| Accuracy  | 0.96  |

---


# Author

Artemiy Korniliev  
ITMO University  
Big Data Infrastructure — Spring 2026