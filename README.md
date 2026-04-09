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

Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Dataset

The model expects images named in the following format:

```text
cat.123.jpg
dog.456.jpg
```

Class is inferred from the filename prefix.

Example dataset structure:

```text
data/
    train/
        cat.1.jpg
        cat.2.jpg
        dog.1.jpg
        dog.2.jpg
```

---

# CLI Usage

The model CLI is implemented in:

```text
src/models/CatVDogModel.py
```

It should be run as a Python module.

General command:

```bash
python -m src.models.CatVDogModel --mode <mode> --path <path>
```

Available modes:

- `train` — train classifier on a dataset
- `single` — predict one image
- `directory` — predict all images in a folder

---

# Training

Train model on a dataset:

```bash
python -m src.models.CatVDogModel \
    --mode train \
    --path data/train \
    --device cpu
```

Example with additional parameters:

```bash
python -m src.models.CatVDogModel \
    --mode train \
    --path data/train \
    --device cpu \
    --data_frac 0.25 \
    --test_size 0.2 \
    --seed 42 \
    --experiments_dir experiments \
    --best_dir experiments \
    --best_metric f1 \
    --skip_errors
```

Training will:

- generate embeddings with ShuffleNet
- split data into train and test
- train Logistic Regression
- compute metrics
- save experiment artifacts
- update the best model if the current one is better

Artifacts created:

```text
experiments/
    exp_0001_YYYY-MM-DD_HH-MM-SS/
        model.pkl
        report.json
```

Best model files:

```text
experiments/
    model.pkl
    model_metrics.json
```

---

# Predict single image

Run prediction for one image:

```bash
python -m src.models.CatVDogModel \
    --mode single \
    --path data/sample/cat.1.jpg \
    --device cpu
```

Example output:

```json
{
  "mode": "single",
  "path": "data/sample/cat.1.jpg",
  "prediction": [0]
}
```

---

# Predict directory

Run predictions for all images in a directory:

```bash
python -m src.models.CatVDogModel \
    --mode directory \
    --path data/sample \
    --device cpu
```

Example with optional flags:

```bash
python -m src.models.CatVDogModel \
    --mode directory \
    --path data/sample \
    --device cpu \
    --recursive \
    --return_paths \
    --skip_errors
```

Optional flags:

- `--recursive` — search files recursively
- `--return_paths` — return file paths with predictions
- `--skip_errors` — skip unreadable or broken images

---

# CLI Arguments

Supported CLI arguments:

```text
--model LOG_REG
--device {cpu,cuda,mps}
--mode {single,directory,train}
--path <path>
--recursive
--return_paths
--skip_errors
--test_size <float>
--seed <int>
--data_frac <float>
--experiments_dir <dir>
--best_dir <dir>
--best_metric {f1,accuracy,precision,recall}
```

---

# API

The project provides a REST API built with **FastAPI**.

Run API locally:

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8001
```

Main endpoint:

```text
POST /predict
```

Request:

```text
multipart/form-data
file=<image>
```

Example request using curl:

```bash
curl -X POST \
  -F "file=@cat.jpg" \
  http://localhost:8001/predict
```

Example response:

```json
{
  "dog_probability": 0.13
}
```

Swagger documentation:

```text
http://localhost:8001/docs
```

---

# Docker

Build Docker image:

```bash
docker build -t catdog-api .
```

Run container:

```bash
docker run -p 8001:8000 catdog-api
```

API will be available at:

```text
http://localhost:8001
```

---

# Redis Setup

The project uses **Redis** to store prediction history.  
Each prediction is saved in Redis and can later be retrieved threw API endpoint:

```text
GET /predictions?limit=N
```

To run redis locally create the following files:

`secrets/redis_host.txt`
```text
redis
```

### `secrets/redis_port.txt`

```text
6379
```

### `secrets/redis_db.txt`

```text
0
```

### `secrets/redis_username.txt`

```text
model_writer
```

### `secrets/redis_password.txt`

```text
strong_password
```

### `secrets/redis_users.acl`

```text
user default off
user model_writer on >strong_password ~prediction:* ~predictions:* +ping +hset +hgetall +zadd +zrevrange +multi +exec +select +client
```

## Redis server config

Create file `redis/redis.conf`:

```conf
aclfile /run/secrets/redis_users_acl
appendonly yes
```
---

## Vault setup

Create file `redis/redis.conf`:

```conf
aclfile /run/secrets/redis_users_acl
appendonly yes
```
---


# Docker Compose

To run the service you need to complete next steps:

Firstly build docker image 
```bash
docker compose build --progress=plain
```
Start vault and redis
```bash
docker compose up -d vault redis
```

Then make bootstrap script executable
```bash
chmod +x scripts/bootstrap_vault.sh
```
Run bootstrap script
```bash
./scripts/bootstrap_vault.sh
```
Then up the Web service:
```bash
docker compose up -d web
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