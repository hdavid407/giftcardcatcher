# Implementation Plan: Discord DM Notifications

## Phase 1: Add discord.py dependency
- Add `discord.py>=2.3.0` to `requirements.txt`
- Install in venv

## Phase 2: Create DiscordNotifier module
- Create `backend/discord_notifier.py`
- Implement `send_match_notification(match_data: dict) -> bool`
- Handle connection, DM creation, embed sending, disconnection
- Graceful error handling for all Discord API failures

## Phase 3: Add Discord config to backend
- Add `discord_bot_token` and `discord_user_id` to `backend/config.py`
- Read from env vars (optional — skip notification if missing)

## Phase 4: Wire notifier into match handler
- Import and call `DiscordNotifier.send_match_notification()` in `backend/websocket.py` `on_match_found`
- Fire-and-forget (don't block Socket.IO handler)

## Phase 5: Update .env with real credentials
- Add `DISCORD_BOT_TOKEN` and `DISCORD_USER_ID` to `.env`
- Update `.env.example` with placeholders

## Phase 6: Test
- Verify import works
- Verify missing config skips silently
- Verify match_found triggers Discord notification
