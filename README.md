# Telegram Gift Card Scraper

Monitors a Telegram bot for specific gift card listings, alerts you in real time, and lets you approve purchases with one tap.

## Architecture

- **Scraper** — Python (Telethon) polls the Telegram bot, parses gift card grids, matches target cards
- **Backend** — Flask + Socket.IO hub, relays events between scraper and frontend
- **Frontend** — React Expo web app deployed to Vercel, shows real-time match alerts

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Copy and fill in your secrets
cp .env.example .env
# Edit .env with your Telegram API credentials and target bot

# 3. Start the backend
python -m backend.run

# 4. In another terminal, start the scraper
python -m scraper.main

# 5. In a third terminal, start the frontend
cd frontend
npm install
npx expo start --web
```

## Environment Variables

See `.env.example` for all required variables.

## Project Structure

```
telegram-buyer/
├── scraper/           # Telegram polling + match logic
│   ├── bot_client.py  # Telethon session manager
│   ├── refresher.py   # Refresh loop
│   ├── matcher.py     # Gift card parser
│   ├── purchaser.py   # Purchase execution
│   ├── ws_client.py   # Socket.IO client to backend
│   ├── config.py      # Scraper env config
│   └── main.py        # Orchestrator
├── backend/           # Flask + Socket.IO server
│   ├── app.py         # App factory
│   ├── routes.py      # REST endpoints
│   ├── websocket.py   # Socket.IO events
│   ├── store.py       # In-memory match state
│   ├── timer.py       # Countdown logic
│   ├── config.py      # Backend env config
│   └── run.py         # Entry point
├── frontend/          # React Expo web app
│   └── ...
├── docs/              # Design docs and plans
├── requirements.txt
├── .env.example
└── README.md
```
