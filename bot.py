#!/usr/bin/python3
from __future__ import annotations

import argparse
from contextlib import suppress
from datetime import datetime
from datetime import timedelta
import fcntl
import hmac
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback
from uuid import uuid4
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from flask import Flask, flash, redirect, render_template, request, session, url_for
from PIL import Image, ImageDraw, ImageFont
import requests
import telebot
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / "token.env"
LAST_UPDATE_ID_FILE = BASE_DIR / "last_update_id.txt"
OFFERTE_ATTIVE_FILE = BASE_DIR / "offerte_attive.json"
LOCK_FILE = Path("/tmp/bot.lock")
BANNER_FILE = BASE_DIR / "offerta_scaduta_banner.png"
UPLOADS_DIR = BASE_DIR / "uploads" / "active"
REQUEST_TIMEOUT = 20
POLL_TIMEOUT = 20
POLL_INTERVAL_SECONDS = 5
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_LOCK_HANDLE = None


def load_env_file(file_path: Path) -> None:
    if not file_path.exists():
        return

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def ensure_runtime_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_json(file_path: Path, default_value):
    try:
        with file_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value


def save_json(file_path: Path, data) -> None:
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, file_path)


def load_last_update_id() -> int | None:
    try:
        return int(LAST_UPDATE_ID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def save_last_update_id(update_id: int | None) -> None:
    if update_id is None:
        return
    temp_path = LAST_UPDATE_ID_FILE.with_suffix(".tmp")
    temp_path.write_text(str(update_id), encoding="utf-8")
    os.replace(temp_path, LAST_UPDATE_ID_FILE)


def normalize_offer(offerta: dict) -> dict:
    message_id = offerta.get("message_id")
    source_image_path = offerta.get("source_image_path")
    return {
        "offer_id": offerta.get("offer_id") or (f"msg-{message_id}" if message_id is not None else uuid4().hex),
        "message_id": message_id,
        "chat_id": offerta.get("chat_id"),
        "scadenza": offerta.get("scadenza"),
        "testo": offerta.get("testo", ""),
        "has_photo": bool(offerta.get("has_photo") or offerta.get("photo_id") or source_image_path),
        "photo_id": offerta.get("photo_id"),
        "source_image_path": source_image_path,
        "created_from_ui": bool(offerta.get("created_from_ui", False)),
        "title": offerta.get("title", ""),
        "description": offerta.get("description", ""),
    }


def load_offers() -> list[dict]:
    raw_offers = load_json(OFFERTE_ATTIVE_FILE, [])
    if not isinstance(raw_offers, list):
        return []
    return [normalize_offer(offerta) for offerta in raw_offers if isinstance(offerta, dict)]


def save_offers(offerte_attive: list[dict]) -> None:
    save_json(OFFERTE_ATTIVE_FILE, offerte_attive)


def get_target_chat_id():
    raw_value = os.environ.get("TELEGRAM_TARGET_CHAT_ID", "").strip()
    if not raw_value:
        return None
    if raw_value.lstrip("-").isdigit():
        return int(raw_value)
    return raw_value


def build_bot() -> telebot.TeleBot:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Telegram bot token not found.")
        sys.exit(1)
    return telebot.TeleBot(token)


def get_dashboard_password() -> str:
    return os.environ.get("DASHBOARD_PASSWORD", "").strip()


def get_web_bind_host() -> str:
    return os.environ.get("WEBAPP_HOST", "127.0.0.1").strip() or "127.0.0.1"


def get_web_bind_port() -> int:
    raw_value = os.environ.get("WEBAPP_PORT", "8080").strip()
    try:
        port = int(raw_value)
    except ValueError:
        return 8080
    if 1 <= port <= 65535:
        return port
    return 8080


def get_app_timezone_name() -> str:
    return os.environ.get("APP_TIMEZONE", "Europe/Rome").strip() or "Europe/Rome"


def get_app_timezone() -> ZoneInfo:
    timezone_name = get_app_timezone_name()
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        print(f"Invalid timezone '{timezone_name}', falling back to Europe/Rome.")
        return ZoneInfo("Europe/Rome")


def current_local_time() -> datetime:
    return datetime.now(get_app_timezone()).replace(tzinfo=None)


load_env_file(ENV_FILE)
ensure_runtime_dirs()
bot = build_bot()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-before-production")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = env_flag("SESSION_COOKIE_SECURE", default=False)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)


def acquire_single_instance_lock() -> None:
    global _LOCK_HANDLE

    _LOCK_HANDLE = LOCK_FILE.open("w")
    try:
        fcntl.flock(_LOCK_HANDLE, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Bot is already running.")
        sys.exit(0)


def estrai_scadenza(testo: str) -> datetime | None:
    match = re.search(r"(?:[Ss]cadenza|[Ee]xpires)\s*:\s*(\d{2}/\d{2}/\d{4}\s*\d{2}[:.]\d{2})", testo)
    if not match:
        return None
    try:
        data_str = match.group(1).replace(".", ":")
        return datetime.strptime(data_str, "%d/%m/%Y %H:%M")
    except ValueError:
        return None


def format_scadenza(scadenza_dt: datetime) -> str:
    return scadenza_dt.strftime("%d/%m/%Y %H:%M")


def resolve_offer_image_path(offerta: dict) -> Path | None:
    raw_path = offerta.get("source_image_path")
    if not raw_path:
        return None
    image_path = Path(raw_path)
    if not image_path.is_absolute():
        image_path = BASE_DIR / image_path
    return image_path


def load_source_image(photo_id: str | None = None, image_path: Path | None = None) -> Image.Image | None:
    if image_path and image_path.exists():
        with Image.open(image_path) as source_image:
            return source_image.convert("RGBA")

    if not photo_id:
        return None

    try:
        file_info = bot.get_file(photo_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        response = requests.get(file_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except Exception as exc:
        print(f"Error while retrieving the image: {exc}")
        return None


def crea_immagine_scaduta(photo_id: str | None = None, image_path: Path | None = None) -> io.BytesIO | None:
    img = load_source_image(photo_id=photo_id, image_path=image_path)
    if img is None:
        return None

    try:
        with Image.open(BANNER_FILE) as banner_image:
            banner = banner_image.convert("RGBA")
            banner = banner.resize(img.size, Image.LANCZOS)
            img_finale = Image.alpha_composite(img, banner)
    except FileNotFoundError:
        img_finale = img.copy()
        draw = ImageDraw.Draw(img_finale)
        try:
            font = ImageFont.truetype("arial.ttf", int(img.height * 0.1))
        except OSError:
            font = ImageFont.load_default()
        text = "Expired Offer"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x_position = (img.width - text_width) // 2
        y_position = (img.height - text_height) // 2
        draw.text((x_position, y_position), text, font=font, fill=(255, 0, 0, 255))

    output = io.BytesIO()
    output.name = "photo.png"
    img_finale.save(output, format="PNG")
    output.seek(0)
    return output


def cleanup_offer_image(offerta: dict) -> None:
    image_path = resolve_offer_image_path(offerta)
    if image_path and image_path.exists():
        with suppress(OSError):
            image_path.unlink()


def cleanup_orphan_uploads(offerte_attive: list[dict]) -> None:
    referenced_paths = set()
    for offerta in offerte_attive:
        image_path = resolve_offer_image_path(offerta)
        if image_path:
            referenced_paths.add(image_path.resolve())

    for file_path in UPLOADS_DIR.glob("*"):
        if file_path.is_file() and file_path.resolve() not in referenced_paths:
            with suppress(OSError):
                file_path.unlink()


def send_offer_to_telegram(chat_id, testo: str, image_path: Path | None = None):
    if image_path and image_path.exists():
        with image_path.open("rb") as image_file:
            return bot.send_photo(chat_id, photo=image_file, caption=testo)
    return bot.send_message(chat_id, testo)


def process_expired_offer(offerta: dict) -> bool:
    try:
        bot.delete_message(chat_id=offerta["chat_id"], message_id=offerta["message_id"])
        nuovo_testo = f"🔴 EXPIRED OFFER 🔴\n\n{offerta['testo']}"
        if offerta.get("has_photo"):
            immagine_scaduta = crea_immagine_scaduta(
                photo_id=offerta.get("photo_id"),
                image_path=resolve_offer_image_path(offerta),
            )
            if immagine_scaduta is not None:
                bot.send_photo(offerta["chat_id"], photo=immagine_scaduta, caption=nuovo_testo)
            else:
                bot.send_message(offerta["chat_id"], nuovo_testo)
        else:
            bot.send_message(offerta["chat_id"], nuovo_testo)
    except Exception as exc:
        if "message to delete not found" not in str(exc):
            print(f"Error while processing expiry for message {offerta.get('message_id')}: {exc}")
            return False

    cleanup_offer_image(offerta)
    return True


def process_expired_offers(offerte_attive: list[dict]) -> list[dict]:
    offerte_rimaste = []
    modified = False
    current_time = current_local_time()

    for offerta in offerte_attive:
        try:
            scadenza_dt = datetime.strptime(offerta["scadenza"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError):
            cleanup_offer_image(offerta)
            modified = True
            continue

        if scadenza_dt <= current_time:
            print(f"Offer {offerta.get('message_id')} expired, starting republish flow.")
            if process_expired_offer(offerta):
                modified = True
                continue

        offerte_rimaste.append(offerta)

    if modified:
        save_offers(offerte_rimaste)

    cleanup_orphan_uploads(offerte_rimaste)
    return offerte_rimaste


def build_offer_text(title: str, description: str, scadenza_dt: datetime) -> str:
    lines = []
    if title.strip():
        lines.append(title.strip())
    if description.strip():
        if lines:
            lines.append("")
        lines.append(description.strip())
    if lines:
        lines.append("")
    lines.append(f"Expires: {format_scadenza(scadenza_dt)}")
    return "\n".join(lines)


def parse_dashboard_expiry(data_value: str, time_value: str) -> datetime:
    return datetime.strptime(f"{data_value} {time_value}", "%Y-%m-%d %H:%M")


def save_uploaded_image(uploaded_file) -> str | None:
    if not uploaded_file or not uploaded_file.filename:
        return None

    filename = secure_filename(uploaded_file.filename)
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image format. Use JPG, PNG, or WEBP.")

    destination = UPLOADS_DIR / f"{uuid4().hex}{extension}"
    uploaded_file.save(destination)
    try:
        with Image.open(destination) as image_file:
            image_file.verify()
    except Exception as exc:
        with suppress(OSError):
            destination.unlink()
        raise ValueError("The uploaded file is not a valid image.") from exc

    return str(destination.relative_to(BASE_DIR))


def create_offer_from_dashboard(form_data, uploaded_file) -> None:
    target_chat_id = get_target_chat_id()
    if target_chat_id is None:
        raise ValueError("Set TELEGRAM_TARGET_CHAT_ID in token.env before publishing.")

    titolo = form_data.get("title", "").strip()
    descrizione = form_data.get("description", "").strip()
    if not titolo and not descrizione:
        raise ValueError("Enter at least a title or a description.")

    data_value = form_data.get("expiry_date", "").strip()
    time_value = form_data.get("expiry_time", "").strip()
    if not data_value or not time_value:
        raise ValueError("Expiry date and time are required.")

    scadenza_dt = parse_dashboard_expiry(data_value, time_value)
    if scadenza_dt <= current_local_time():
        raise ValueError("Expiry must be in the future.")

    source_image_path = save_uploaded_image(uploaded_file)
    testo = build_offer_text(titolo, descrizione, scadenza_dt)

    try:
        sent_message = send_offer_to_telegram(
            chat_id=target_chat_id,
            testo=testo,
            image_path=BASE_DIR / source_image_path if source_image_path else None,
        )
    except Exception:
        if source_image_path:
            cleanup_offer_image({"source_image_path": source_image_path})
        raise

    offerte_attive = load_offers()
    nuova_offerta = normalize_offer(
        {
            "offer_id": uuid4().hex,
            "message_id": sent_message.message_id,
            "chat_id": sent_message.chat.id,
            "scadenza": scadenza_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "testo": testo,
            "has_photo": bool(getattr(sent_message, "photo", None) or source_image_path),
            "photo_id": sent_message.photo[-1].file_id if getattr(sent_message, "photo", None) else None,
            "source_image_path": source_image_path,
            "created_from_ui": True,
            "title": titolo,
            "description": descrizione,
        }
    )
    offerte_attive.append(nuova_offerta)
    save_offers(offerte_attive)
    cleanup_orphan_uploads(offerte_attive)


def force_expire_offer(offer_id: str) -> bool:
    offerte_attive = load_offers()
    offerte_rimaste = []
    target_offer = None

    for offerta in offerte_attive:
        if offerta.get("offer_id") == offer_id:
            target_offer = offerta
            continue
        offerte_rimaste.append(offerta)

    if target_offer is None:
        return False

    if not process_expired_offer(target_offer):
        return False

    save_offers(offerte_rimaste)
    cleanup_orphan_uploads(offerte_rimaste)
    return True


def is_dashboard_authenticated() -> bool:
    return bool(session.get("dashboard_authenticated"))


@app.before_request
def require_dashboard_login():
    if request.endpoint in {None, "login", "login_post", "logout", "static"}:
        return None
    if is_dashboard_authenticated():
        return None
    return redirect(url_for("login", next=request.path))


def sort_offers(offerte_attive: list[dict]) -> list[dict]:
    def sort_key(offerta: dict):
        try:
            return datetime.strptime(offerta["scadenza"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError):
            return datetime.max

    return sorted(offerte_attive, key=sort_key)


def sync_offer_from_channel_post(offerte_attive: list[dict], messaggio, testo: str, is_edited: bool) -> list[dict]:
    msg_id = messaggio.message_id

    if is_edited:
        offerta_da_aggiornare = None
        for offerta in offerte_attive:
            if offerta["message_id"] == msg_id:
                offerta_da_aggiornare = offerta
                break

        if offerta_da_aggiornare:
            nuova_scadenza = estrai_scadenza(testo)
            if nuova_scadenza:
                offerta_da_aggiornare["scadenza"] = nuova_scadenza.strftime("%Y-%m-%d %H:%M:%S")
                offerta_da_aggiornare["testo"] = testo
                save_offers(offerte_attive)
            else:
                cleanup_offer_image(offerta_da_aggiornare)
                offerte_attive = [offerta for offerta in offerte_attive if offerta["message_id"] != msg_id]
                save_offers(offerte_attive)
        return offerte_attive

    if any(offerta["message_id"] == msg_id for offerta in offerte_attive):
        return offerte_attive

    scadenza = estrai_scadenza(testo)
    if scadenza and scadenza > current_local_time():
        offerte_attive.append(
            normalize_offer(
                {
                    "message_id": msg_id,
                    "chat_id": messaggio.chat.id,
                    "scadenza": scadenza.strftime("%Y-%m-%d %H:%M:%S"),
                    "testo": testo,
                    "has_photo": bool(messaggio.photo),
                    "photo_id": messaggio.photo[-1].file_id if messaggio.photo else None,
                }
            )
        )
        save_offers(offerte_attive)
    return offerte_attive


def run_bot_loop() -> None:
    acquire_single_instance_lock()
    last_update_id = load_last_update_id()
    offerte_attive = load_offers()
    offerte_attive = process_expired_offers(offerte_attive)
    print(f"Bot started. Active offers in memory: {len(offerte_attive)}. Application timezone: {get_app_timezone_name()}")

    while True:
        print("\n--- Starting new check ---")
        try:
            offerte_attive = process_expired_offers(load_offers())
            offset_da_usare = last_update_id + 1 if last_update_id is not None else None
            updates = bot.get_updates(
                offset=offset_da_usare,
                timeout=POLL_TIMEOUT,
                allowed_updates=["channel_post", "edited_channel_post"],
            )

            for update in updates:
                last_update_id = update.update_id
                messaggio = update.channel_post or update.edited_channel_post
                if not messaggio:
                    continue

                testo = messaggio.caption or messaggio.text or ""
                offerte_attive = sync_offer_from_channel_post(
                    offerte_attive,
                    messaggio,
                    testo,
                    is_edited=bool(update.edited_channel_post),
                )
        except Exception as exc:
            print(f"Fatal error: {exc}")
            traceback.print_exc()
        finally:
            save_last_update_id(last_update_id)
            cleanup_orphan_uploads(load_offers())
            print(f"--- Check complete. Waiting {POLL_INTERVAL_SECONDS} seconds. ---")
            time.sleep(POLL_INTERVAL_SECONDS)


@app.get("/")
def dashboard():
    offerte_attive = sort_offers(load_offers())
    return render_template(
        "dashboard.html",
        offers=offerte_attive,
        target_chat_id=get_target_chat_id(),
        now=datetime.now(),
    )


@app.get("/login")
def login():
    if is_dashboard_authenticated():
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.post("/login")
def login_post():
    dashboard_password = get_dashboard_password()
    submitted_password = request.form.get("password", "")

    if not dashboard_password:
        flash("Set DASHBOARD_PASSWORD in token.env before exposing the dashboard.", "error")
        return redirect(url_for("login"))

    if not hmac.compare_digest(submitted_password, dashboard_password):
        flash("Invalid password.", "error")
        return redirect(url_for("login"))

    session.clear()
    session["dashboard_authenticated"] = True
    session.permanent = True
    next_path = request.args.get("next") or request.form.get("next") or url_for("dashboard")
    if not next_path.startswith("/"):
        next_path = url_for("dashboard")
    return redirect(next_path)


@app.post("/logout")
def logout():
    session.clear()
    flash("Signed out successfully.", "success")
    return redirect(url_for("login"))


@app.post("/offers")
def publish_offer():
    try:
        create_offer_from_dashboard(request.form, request.files.get("image"))
        flash("Offer published successfully.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        flash(f"Error while publishing the offer: {exc}", "error")
    return redirect(url_for("dashboard"))


@app.post("/offers/<offer_id>/expire")
def expire_offer_now(offer_id: str):
    if force_expire_offer(offer_id):
        flash("Offer marked as expired and removed from the active queue.", "success")
    else:
        flash("Could not force expiry for this offer.", "error")
    return redirect(url_for("dashboard"))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram offers bot with web dashboard.")
    subparsers = parser.add_subparsers(dest="mode")

    subparsers.add_parser("bot", help="Start the worker loop for expiries and Telegram updates.")

    web_parser = subparsers.add_parser("web", help="Start the web dashboard for creating offers.")
    web_parser.add_argument("--host", default=get_web_bind_host())
    web_parser.add_argument("--port", default=get_web_bind_port(), type=int)

    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.mode in (None, "bot"):
        run_bot_loop()
        return

    if args.mode == "web":
        if not get_dashboard_password():
            print("DASHBOARD_PASSWORD is not configured. Set it in token.env before starting the dashboard.")
            sys.exit(1)
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()