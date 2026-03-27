# Contributing

Thanks for contributing.

## Development Setup

1. Create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `token.env.example` to `token.env`.
4. Fill in valid Telegram and dashboard settings.

Example:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp token.env.example token.env
```

## Project Scope

This project focuses on:

- publishing offers to Telegram from a protected dashboard
- tracking expiry times
- republishing expired offers automatically
- cleaning up uploaded media after expiry

Please keep contributions aligned with that scope.

## Pull Request Guidelines

1. Keep changes focused and minimal.
2. Avoid unrelated refactors.
3. Preserve the existing deployment flow for Ubuntu and Cloudflare Tunnel.
4. Update `README.md` when behavior or configuration changes.
5. Do not commit secrets, local runtime files, or generated uploads.

## Code Style

- Prefer small, explicit functions.
- Keep environment-based configuration simple.
- Preserve compatibility with both worker mode and web mode.
- When adding user-facing strings, keep the public project language in English.

## Testing Checklist

Before opening a pull request, verify at least the following:

1. `python bot.py web` starts correctly with a valid `token.env`.
2. `python bot.py bot` starts correctly with the same configuration.
3. A new offer can be created from the dashboard.
4. Forced expiry still works.
5. Automatic expiry still works with the configured `APP_TIMEZONE`.