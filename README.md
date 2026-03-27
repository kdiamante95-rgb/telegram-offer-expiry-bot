# Bot Telegram Offerte

## Italiano

Bot Telegram per pubblicare offerte su un canale, monitorarne la scadenza e ripubblicarle automaticamente come scadute. Include anche una dashboard web protetta da password per creare offerte con data, ora e immagine.

### Funzionalita

- Pubblicazione offerte da dashboard web
- Supporto immagini con riuso alla scadenza
- Ripubblicazione automatica delle offerte scadute
- Cleanup automatico dei file immagine locali dopo la scadenza
- Login applicativo per la dashboard
- Supporto deploy su Ubuntu con `systemd`
- Supporto esposizione tramite Cloudflare Tunnel

### Struttura

- `bot.py`: logica del worker Telegram e dashboard Flask
- `templates/` e `static/`: interfaccia web
- `token.env.example`: esempio di configurazione
- `deploy/`: script e unit file per Ubuntu

### Requisiti

- Python 3.11+
- Un bot Telegram con permessi sul canale
- Il bot deve essere admin del canale se vuoi pubblicare dalla dashboard

### Setup Locale

1. Crea un virtualenv.
2. Installa le dipendenze da `requirements.txt`.
3. Copia `token.env.example` in `token.env`.
4. Compila le variabili d'ambiente.

Esempio:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy token.env.example token.env
```

### Configurazione

Il file `token.env` viene caricato automaticamente all'avvio. Variabili supportate:

- `TELEGRAM_BOT_TOKEN`: token del bot Telegram
- `TELEGRAM_TARGET_CHAT_ID`: username del canale tipo `@miocanale` oppure `chat_id` numerico
- `FLASK_SECRET_KEY`: chiave per la sessione Flask
- `DASHBOARD_PASSWORD`: password di accesso alla dashboard
- `SESSION_COOKIE_SECURE`: `true` se la dashboard passa sotto HTTPS
- `WEBAPP_HOST`: host di bind della webapp
- `WEBAPP_PORT`: porta di bind della webapp
- `APP_TIMEZONE`: timezone applicativa usata per confrontare le scadenze

Esempio:

```env
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_TARGET_CHAT_ID=@miocanale
FLASK_SECRET_KEY=una-chiave-lunga-casuale
DASHBOARD_PASSWORD=una-password-lunga
SESSION_COOKIE_SECURE=true
WEBAPP_HOST=127.0.0.1
WEBAPP_PORT=8080
APP_TIMEZONE=Europe/Rome
```

### Avvio

Worker Telegram:

```bash
python bot.py bot
```

Dashboard web:

```bash
python bot.py web
```

Override temporaneo di host e porta:

```bash
python bot.py web --host 127.0.0.1 --port 8080
```

### Note Sulla Scadenza

Le scadenze sono confrontate usando `APP_TIMEZONE`. Se il server gira in UTC ma vuoi ragionare con l'ora italiana, imposta `APP_TIMEZONE=Europe/Rome`.

### Deploy Ubuntu

Sono inclusi file di supporto per il deploy:

- `deploy/setup_ubuntu.sh`
- `deploy/systemd/telegram-bot.service`
- `deploy/systemd/telegram-web.service`

Flusso tipico:

1. Copia il progetto in `/opt/bot_telegram`.
2. Esegui `bash deploy/setup_ubuntu.sh`.
3. Crea `/opt/bot_telegram/token.env` partendo da `token.env.example`.
4. Copia i file `systemd` in `/etc/systemd/system/`.
5. Esegui `sudo systemctl daemon-reload`.
6. Avvia i servizi con `sudo systemctl enable --now telegram-bot.service telegram-web.service`.

Se usi Cloudflare Tunnel, puoi lasciare la dashboard su `127.0.0.1` e puntare il tunnel a `http://127.0.0.1:8080` oppure alla porta definita in `WEBAPP_PORT`.

### File Runtime

I file runtime come `token.env`, `offerte_attive.json`, `last_update_id.txt`, `uploads/` e ambienti virtuali non vanno committati. Il `.gitignore` del progetto li esclude gia.

---

## English

Telegram bot for publishing offers to a channel, tracking their expiry time, and automatically republishing them as expired. It also includes a password-protected web dashboard for creating offers with date, time, and image.

### Features

- Publish offers from a web dashboard
- Image support with image reuse on expiry
- Automatic republishing of expired offers
- Automatic cleanup of local uploaded images after expiry
- Application-level login for the dashboard
- Ubuntu deployment support with `systemd`
- Cloudflare Tunnel friendly deployment

### Structure

- `bot.py`: Telegram worker and Flask dashboard logic
- `templates/` and `static/`: web interface
- `token.env.example`: configuration example
- `deploy/`: Ubuntu scripts and unit files

### Requirements

- Python 3.11+
- A Telegram bot with channel permissions
- The bot must be an admin in the channel if you want to publish from the dashboard

### Local Setup

1. Create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `token.env.example` to `token.env`.
4. Fill in the environment variables.

Example:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp token.env.example token.env
```

### Configuration

The `token.env` file is loaded automatically on startup. Supported variables:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_TARGET_CHAT_ID`: channel username like `@yourchannel` or a numeric `chat_id`
- `FLASK_SECRET_KEY`: Flask session secret key
- `DASHBOARD_PASSWORD`: dashboard access password
- `SESSION_COOKIE_SECURE`: set to `true` when the dashboard is served over HTTPS
- `WEBAPP_HOST`: web app bind host
- `WEBAPP_PORT`: web app bind port
- `APP_TIMEZONE`: application timezone used for expiry comparisons

Example:

```env
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_TARGET_CHAT_ID=@yourchannel
FLASK_SECRET_KEY=a-long-random-secret-key
DASHBOARD_PASSWORD=a-long-password
SESSION_COOKIE_SECURE=true
WEBAPP_HOST=127.0.0.1
WEBAPP_PORT=8080
APP_TIMEZONE=Europe/Rome
```

### Running

Telegram worker:

```bash
python bot.py bot
```

Web dashboard:

```bash
python bot.py web
```

Temporary host and port override:

```bash
python bot.py web --host 127.0.0.1 --port 8080
```

### Expiry Notes

Expiry comparisons use `APP_TIMEZONE`. If your server runs in UTC but you want to work with Italian local time, set `APP_TIMEZONE=Europe/Rome`.

### Ubuntu Deployment

Deployment support files are included:

- `deploy/setup_ubuntu.sh`
- `deploy/systemd/telegram-bot.service`
- `deploy/systemd/telegram-web.service`

Typical flow:

1. Copy the project to `/opt/bot_telegram`.
2. Run `bash deploy/setup_ubuntu.sh`.
3. Create `/opt/bot_telegram/token.env` starting from `token.env.example`.
4. Copy the `systemd` files into `/etc/systemd/system/`.
5. Run `sudo systemctl daemon-reload`.
6. Start the services with `sudo systemctl enable --now telegram-bot.service telegram-web.service`.

If you use Cloudflare Tunnel, you can keep the dashboard bound to `127.0.0.1` and point the tunnel to `http://127.0.0.1:8080` or the port defined in `WEBAPP_PORT`.

### Runtime Files

Runtime files such as `token.env`, `offerte_attive.json`, `last_update_id.txt`, `uploads/`, and virtual environments should not be committed. The project `.gitignore` already excludes them.