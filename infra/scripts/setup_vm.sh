#!/usr/bin/env bash
# Runs ON the target VM (via SSH from the CI pipeline) to install every
# dependency and deploy Candidate True Companion's backend + database.
# See docs/Architecture-Decisions.md §10/§11.
#
# Assumes the CI pipeline has already copied, to this VM, under APP_DIR:
#   backend/           (app code, including a real backend/.env with secrets)
#   infra/              (docker-compose.yml + a real infra/.env with POSTGRES_PASSWORD)
#   infra/systemd/candidate-true-companion-api.service
#
# Idempotent: safe to re-run for redeploys — installs are skipped if already
# present, docker compose / systemctl calls converge rather than duplicate.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/candidate-true-companion}"
SERVICE_NAME="candidate-true-companion-api"
PYTHON_BIN="python3"

echo "== apt update/upgrade dependencies =="
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg git \
  python3 python3-venv python3-pip \
  nginx

echo "== Docker =="
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "== Postgres via docker compose (infra/docker-compose.yml) =="
cd "$APP_DIR/infra"
sudo docker compose --env-file .env -f docker-compose.yml up -d

echo "== Waiting for Postgres to report healthy =="
for _ in $(seq 1 30); do
  status=$(sudo docker inspect --format='{{.State.Health.Status}}' infra-postgres-1 2>/dev/null || echo "starting")
  if [ "$status" = "healthy" ]; then
    echo "Postgres healthy."
    break
  fi
  sleep 2
done

echo "== Python venv + backend dependencies =="
cd "$APP_DIR/backend"
if [ ! -d venv ]; then
  "$PYTHON_BIN" -m venv venv
fi
./venv/bin/pip install --upgrade pip --quiet
./venv/bin/pip install -r requirements.txt --quiet

echo "== Alembic migrations =="
./venv/bin/python -m alembic upgrade head

echo "== systemd service =="
sudo cp "$APP_DIR/infra/systemd/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "== Nginx reverse proxy =="
sudo cp "$APP_DIR/infra/nginx/candidate-true-companion.conf" /etc/nginx/sites-available/candidate-true-companion.conf
sudo ln -sf /etc/nginx/sites-available/candidate-true-companion.conf /etc/nginx/sites-enabled/candidate-true-companion.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "== Service status =="
sudo systemctl --no-pager status "$SERVICE_NAME" || true

echo "== Done =="
