#!/usr/bin/env bash
# Runs ON the target VM (via SSH from the CI pipeline) to install every
# dependency and deploy Candidate True Companion's backend + database.
# See docs/Architecture-Decisions.md §10/§11.
#
# Optional env vars (from the workflow):
#   DOMAIN_NAME          hostname for HTTPS, e.g. <label>.centralindia.cloudapp.azure.com
#   LETSENCRYPT_EMAIL    contact address for Let's Encrypt (required with DOMAIN_NAME)
# Without DOMAIN_NAME the site is served over plain HTTP only (the browser
# will not allow microphone access on it).
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
  nginx certbot

echo "== Node.js (runs the Next.js frontend) =="
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

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

echo "== systemd services =="
for unit in candidate-true-companion-api candidate-true-companion-web; do
  sudo cp "$APP_DIR/infra/systemd/${unit}.service" "/etc/systemd/system/${unit}.service"
done
sudo systemctl daemon-reload
for unit in candidate-true-companion-api candidate-true-companion-web; do
  sudo systemctl enable "$unit"
  sudo systemctl restart "$unit"
done

echo "== Nginx reverse proxy =="
DOMAIN_NAME="${DOMAIN_NAME:-}"
SERVER_NAME="${DOMAIN_NAME:-_}"
NGINX_SRC="$APP_DIR/infra/nginx"
sudo mkdir -p /etc/nginx/snippets /var/www/certbot
sudo cp "$NGINX_SRC/candidate-true-companion-locations.conf" /etc/nginx/snippets/candidate-true-companion-locations.conf
sudo rm -f /etc/nginx/sites-enabled/default

render_site() {  # $1 = template file
  sed "s/__SERVER_NAME__/${SERVER_NAME}/g" "$NGINX_SRC/$1" | sudo tee /etc/nginx/sites-available/candidate-true-companion.conf >/dev/null
  sudo ln -sf /etc/nginx/sites-available/candidate-true-companion.conf /etc/nginx/sites-enabled/candidate-true-companion.conf
  sudo nginx -t
  sudo systemctl enable nginx
  sudo systemctl reload nginx 2>/dev/null || sudo systemctl restart nginx
}

if [ -n "$DOMAIN_NAME" ] && [ -f "/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ]; then
  echo "Certificate for ${DOMAIN_NAME} exists - serving HTTPS."
  render_site candidate-true-companion-ssl.conf
else
  render_site candidate-true-companion.conf
  if [ -n "$DOMAIN_NAME" ]; then
    : "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL is required with DOMAIN_NAME}"
    echo "== Requesting a Let's Encrypt certificate for ${DOMAIN_NAME} =="
    sudo certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN_NAME"       --non-interactive --agree-tos -m "$LETSENCRYPT_EMAIL"       --deploy-hook "systemctl reload nginx"
    render_site candidate-true-companion-ssl.conf
  else
    echo "No DOMAIN_NAME set - serving plain HTTP only (no microphone access in browsers)."
  fi
fi

echo "== Service status =="
sudo systemctl --no-pager status "$SERVICE_NAME" candidate-true-companion-web || true

echo "== Done =="
