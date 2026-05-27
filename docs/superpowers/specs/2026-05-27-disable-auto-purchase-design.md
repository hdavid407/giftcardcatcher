# Disable Automatic Purchase Button Click

**Date**: 2026-05-27
**Status**: Approved

## Overview

The `purchase_card` WebSocket handler in `scraper/main.py` currently clicks the Purchase button via `purchaser.purchase()`. Disable this so the scraper logs the request but takes no action. This keeps the full purchase flow wired up for easy re-enable later.

## Change

In `scraper/main.py` `handle_purchase()`:
- Log the request
- Skip `purchaser.purchase()` call
- Skip `bot_client.go_back_to_listings()` call
- Keep all imports and handler wiring intact

## Re-enabling Later

Uncomment the `purchaser.purchase()` and `go_back_to_listings()` lines in `handle_purchase()`.
