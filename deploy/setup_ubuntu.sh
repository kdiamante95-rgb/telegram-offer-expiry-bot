#!/usr/bin/env bash
set -euo pipefail

APP_USER="telegrambot"
APP_GROUP="telegrambot"
APP_ROOT="/opt/bot_telegram"
PYTHON_BIN="python3"

echo "[1/7] Installing base packages"
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

echo "[2/7] Creating service user and group"
if ! getent group "$APP_GROUP" >/dev/null; then
  sudo groupadd --system "$APP_GROUP"
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  sudo useradd --system --gid "$APP_GROUP" --home-dir "$APP_ROOT" --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "[3/7] Creating application directories"
sudo mkdir -p "$APP_ROOT"
sudo mkdir -p "$APP_ROOT/uploads/active"
sudo chown -R "$APP_USER:$APP_GROUP" "$APP_ROOT"

echo "[4/7] Copy the project files into $APP_ROOT before proceeding"
echo "    Example: sudo rsync -av ./ $APP_ROOT/"

echo "[5/7] Creating virtual environment"
sudo -u "$APP_USER" "$PYTHON_BIN" -m venv "$APP_ROOT/venv"

echo "[6/7] Upgrading pip and installing dependencies"
sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install -r "$APP_ROOT/requirements.txt"

echo "[7/7] Final checks"
echo "- Create $APP_ROOT/token.env from token.env.example"
echo "- Copy the systemd files from deploy/systemd/ into /etc/systemd/system/"
echo "- If you use Cloudflare Tunnel, you do not need Nginx"
echo "- If you want a local reverse proxy, an example config is available in deploy/nginx/"
echo "- Then run: sudo systemctl daemon-reload"
echo "- Then run: sudo systemctl enable --now telegram-bot.service telegram-web.service"