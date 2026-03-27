# Bot Telegram Offerte

Bot Telegram per pubblicare offerte su un canale, monitorarne la scadenza e ripubblicarle automaticamente come scadute. Include anche una dashboard web protetta da password per creare le offerte con data, ora e immagine.

## Funzionalita

- Pubblicazione offerte da dashboard web
- Supporto immagini con riuso dell'immagine alla scadenza
- Ripubblicazione automatica dell'offerta come scaduta
- Cleanup automatico dei file immagine locali dopo la scadenza
- Login applicativo per la dashboard
- Supporto deploy su Ubuntu con `systemd`
- Supporto esposizione tramite Cloudflare Tunnel

## Struttura

- `bot.py`: logica del worker Telegram e dashboard Flask
- `templates/` e `static/`: interfaccia web
- `token.env.example`: esempio di configurazione
- `deploy/`: script e unit file per Ubuntu

## Requisiti

- Python 3.11+
- Un bot Telegram con permessi sul canale
- Il bot deve essere admin del canale se vuoi pubblicare dalla dashboard

## Setup Locale

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

## Configurazione

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

## Avvio

Worker Telegram:

```bash
python bot.py bot
```

Dashboard web:

```bash
python bot.py web
```

Puoi anche fare override temporaneo di host e porta:

```bash
python bot.py web --host 127.0.0.1 --port 8080
```

## Note Sulla Scadenza

Le scadenze sono confrontate usando `APP_TIMEZONE`. Se il server gira in UTC ma vuoi ragionare con l'ora italiana, imposta `APP_TIMEZONE=Europe/Rome`.

## Deploy Ubuntu

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

## File Runtime

I file runtime come `token.env`, `offerte_attive.json`, `last_update_id.txt`, `uploads/` e ambienti virtuali non vanno committati. Il `.gitignore` del progetto li esclude gia.