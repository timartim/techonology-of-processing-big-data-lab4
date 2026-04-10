#!/usr/bin/env bash
set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_CONTAINER="${VAULT_CONTAINER:-vault}"
OUT_DIR="${OUT_DIR:-.vault-local}"
POLICY_FILE="${POLICY_FILE:-vault/catdog-web-policy.hcl}"

REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"
REDIS_USERNAME="${REDIS_USERNAME:-model_writer}"
REDIS_PASSWORD="${REDIS_PASSWORD:-strong_password}"

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
KAFKA_TOPIC_PREDICTIONS="${KAFKA_TOPIC_PREDICTIONS:-predictions.created}"
KAFKA_CONSUMER_GROUP="${KAFKA_CONSUMER_GROUP:-catdog-consumer}"

mkdir -p "$OUT_DIR"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Не найдена команда: $1"
    exit 1
  }
}

need_cmd docker
need_cmd python3

vault_exec() {
  docker compose exec -T "$VAULT_CONTAINER" sh -lc "export VAULT_ADDR='$VAULT_ADDR'; $*"
}

status_json() {
  vault_exec "vault status -format=json" 2>/dev/null || true
}

python_json_field() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
file_path = sys.argv[1]
expr = sys.argv[2]
data = json.load(open(file_path, "r", encoding="utf-8"))
cur = data
for part in expr.split("."):
    if part.isdigit():
        cur = cur[int(part)]
    else:
        cur = cur[part]
print(cur)
PY
}

is_initialized() {
  local raw
  raw="$(status_json)"
  if [[ -z "$raw" ]]; then
    echo "false"
    return
  fi
  python3 -c 'import sys, json; print("true" if json.load(sys.stdin)["initialized"] else "false")' <<< "$raw"
}

is_sealed() {
  local raw
  raw="$(status_json)"
  if [[ -z "$raw" ]]; then
    echo "true"
    return
  fi
  python3 -c 'import sys, json; print("true" if json.load(sys.stdin)["sealed"] else "false")' <<< "$raw"
}

wait_for_vault() {
  echo "Жду Vault..."
  for _ in $(seq 1 60); do
    rc=0
    docker compose exec -T "$VAULT_CONTAINER" sh -lc \
      "export VAULT_ADDR='$VAULT_ADDR'; vault status >/dev/null 2>&1" || rc=$?

    if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then
      echo "Vault отвечает"
      return 0
    fi

    sleep 2
  done

  echo "Vault не отвечает"
  docker compose logs "$VAULT_CONTAINER" || true
  exit 1
}

init_if_needed() {
  if [[ "$(is_initialized)" == "false" ]]; then
    echo "Vault не initialized. Выполняю init..."
    vault_exec "vault operator init -format=json" > "$OUT_DIR/init.json"
    chmod 600 "$OUT_DIR/init.json"
    echo "Сохранил init result в $OUT_DIR/init.json"
  else
    echo "Vault уже initialized"
  fi
}

unseal_if_needed() {
  if [[ "$(is_sealed)" == "true" ]]; then
    if [[ ! -f "$OUT_DIR/init.json" ]]; then
      echo "Vault sealed, но $OUT_DIR/init.json не найден."
      echo "Без сохраненных unseal keys автоматический unseal невозможен."
      echo "Сбрось volume Vault и запусти скрипт заново."
      exit 1
    fi

    echo "Vault sealed. Выполняю unseal..."
    for i in 0 1 2; do
      key="$(python_json_field "$OUT_DIR/init.json" "unseal_keys_b64.$i")"
      vault_exec "vault operator unseal '$key' >/dev/null"
    done
    echo "Unseal завершен"
  else
    echo "Vault уже unsealed"
  fi
}

get_root_token() {
  if [[ -n "${VAULT_TOKEN:-}" ]]; then
    printf "%s" "$VAULT_TOKEN"
    return
  fi

  if [[ -f "$OUT_DIR/init.json" ]]; then
    python_json_field "$OUT_DIR/init.json" "root_token"
    return
  fi

  echo "Не найден root token. Установи VAULT_TOKEN или сохрани init.json" >&2
  exit 1
}

ensure_token_works() {
  local token="$1"
  vault_exec "export VAULT_TOKEN='$token'; vault token lookup >/dev/null"
}

enable_kv_and_approle() {
  local token="$1"
  vault_exec "export VAULT_TOKEN='$token'; vault secrets enable -path=app kv-v2 >/dev/null 2>&1 || true"
  vault_exec "export VAULT_TOKEN='$token'; vault auth enable approle >/dev/null 2>&1 || true"
}

write_redis_secret() {
  local token="$1"
  vault_exec "export VAULT_TOKEN='$token'; vault kv put -mount=app catdog/redis \
    host='$REDIS_HOST' \
    port='$REDIS_PORT' \
    db='$REDIS_DB' \
    username='$REDIS_USERNAME' \
    password='$REDIS_PASSWORD' >/dev/null"
}

write_kafka_secret() {
  local token="$1"
  vault_exec "export VAULT_TOKEN='$token'; vault kv put -mount=app catdog/kafka \
    bootstrapServers='$KAFKA_BOOTSTRAP_SERVERS' \
    topicPredictions='$KAFKA_TOPIC_PREDICTIONS' \
    consumerGroup='$KAFKA_CONSUMER_GROUP' >/dev/null"
}


write_policy_and_role() {
  local token="$1"

  if [[ ! -f "$POLICY_FILE" ]]; then
    echo "Не найден policy file: $POLICY_FILE"
    exit 1
  fi

  docker compose exec -T "$VAULT_CONTAINER" sh -lc "cat > /tmp/catdog-web-policy.hcl" < "$POLICY_FILE"

  vault_exec "export VAULT_TOKEN='$token'; vault policy write catdog-web /tmp/catdog-web-policy.hcl >/dev/null"

  vault_exec "export VAULT_TOKEN='$token'; vault write auth/approle/role/catdog-web \
    token_policies='catdog-web' \
    token_type='batch' \
    secret_id_ttl='24h' \
    token_ttl='1h' \
    token_max_ttl='4h' >/dev/null"

  vault_exec "export VAULT_TOKEN='$token'; vault read -field=role_id auth/approle/role/catdog-web/role-id" > "$OUT_DIR/role_id"
  vault_exec "export VAULT_TOKEN='$token'; vault write -f -field=secret_id auth/approle/role/catdog-web/secret-id" > "$OUT_DIR/secret_id"

  chmod 600 "$OUT_DIR/role_id" "$OUT_DIR/secret_id"
}

main() {
  wait_for_vault
  init_if_needed
  unseal_if_needed

  local token
  token="$(get_root_token)"
  ensure_token_works "$token"

  echo "Включаю KV v2 и AppRole..."
  enable_kv_and_approle "$token"

  echo "Записываю Redis secret..."
  write_redis_secret "$token"

  echo "Записываю Kafka secret..."
  write_kafka_secret "$token"

  echo "Создаю policy и role..."
  write_policy_and_role "$token"

  echo
  echo "Готово."
  echo "Секрет Redis: app/catdog/redis"
  echo "Секрет Kafka: app/catdog/kafka"
  echo "init.json:   $OUT_DIR/init.json"
  echo "role_id:     $OUT_DIR/role_id"
  echo "secret_id:   $OUT_DIR/secret_id"
}

main "$@"