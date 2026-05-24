# Discord DM Notifications for Gift Card Matches

## Overview
Send a Discord direct message to the user whenever the scraper finds a matching gift card. The notification is sent from the backend when it receives a `match_found` event from the scraper via Socket.IO.

## Goals
- Notify the user immediately when a target gift card is found
- Keep the notification lightweight and non-blocking
- Handle Discord API errors gracefully without crashing the backend

## Non-Goals
- Persistent Discord bot connection (connect-on-demand only)
- Two-way Discord interaction (no commands, no replies)
- Notifications for non-match events (errors, state changes)

## Architecture

### Component: DiscordNotifier
A new module `backend/discord_notifier.py` that encapsulates all Discord interaction.

**Responsibility:** Connect to Discord, send a DM, disconnect.
**Interface:** `async def send_match_notification(match_data: dict) -> bool`
**Dependencies:** `discord.py` library, Discord bot token, target user ID.

### Flow
```
Scraper finds match
    → emits "match_found" via Socket.IO
    → Backend websocket handler receives it
    → Backend calls DiscordNotifier.send_match_notification()
    → Discord bot connects → fetches user → sends embed DM → disconnects
    → Returns True/False to backend (logged, not blocking)
```

### Message Format
Discord embed with:
- **Title:** 🎯 Gift Card Match Found!
- **Description:** A card matching your target criteria was detected.
- **Fields:**
  - BIN: `435880xx`
  - Amount: `USD $50.00`
  - Discount: `39%`
  - Timestamp: `2026-05-24 14:32:00 UTC`
- **Color:** Green (`0x00FF00`)
- **Footer:** Telegram Gift Card Buyer

## Configuration

Add to `.env`:
```
DISCORD_BOT_TOKEN=N5Db-Xj-M8_-yJd_BRDU2DAssq6aVbGU
DISCORD_USER_ID=987894235627913236
```

Add to `.env.example`:
```
DISCORD_BOT_TOKEN=
DISCORD_USER_ID=
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Discord API down | Log warning, return False, backend continues |
| User has DMs disabled | Log warning, return False |
| Invalid bot token | Log error on first use, return False |
| Missing config (token or user ID) | Skip Discord notification silently |

## Files Changed

| File | Change |
|------|--------|
| `backend/discord_notifier.py` | New module — Discord client wrapper |
| `backend/websocket.py` | Call notifier in `on_match_found` handler |
| `backend/config.py` | Add `discord_bot_token` and `discord_user_id` |
| `requirements.txt` | Add `discord.py>=2.3.0` |
| `.env.example` | Add Discord config placeholders |

## Testing Plan

1. **Unit test:** Mock `discord.Client` to verify `send_match_notification` calls `create_dm` and `send` with correct embed.
2. **Integration test:** Trigger a fake `match_found` event and verify the Discord API receives the request (using a test bot in a private server).
3. **Error test:** Verify missing config skips notification, invalid token logs error.
