# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pyslackrandomcoffee is a Slack bot that randomly pairs channel members for coffee dates. It posts matches back to the channel and avoids repeating recent pairs by analyzing channel history.

The bot can operate in two modes:
- **Public pairs**: Pairs posted in the main channel (for history tracking)
- **Private pairs**: Pairs posted to a private memory channel, with DMs sent to each pair

## Environment Setup

### Using Conda (Recommended)
```bash
conda env create -n pyslackrandomcoffee -f pyslackrandomcoffee.yml
conda activate pyslackrandomcoffee
```

### Using pip
```bash
pip install -r requirements.txt
```

### Configuration
Copy `.env.template` to `.env` and configure:
- `SLACK_API_TOKEN`: Bot User OAuth Token (xoxb-...)
- `CHANNEL_NAME`: Main channel for pairing
- `LOOKBACK_DAYS`: Days to look back for previous pairs (default: 28)
- `MAGICAL_TEXT`: Text used to identify pair messages in history
- `PAIRS_ARE_PUBLIC`: Whether pairs are posted publicly or privately
- `PRIVATE_CHANNEL_NAME_FOR_MEMORY`: Private channel for pair history (if not public)
- `CHAN_NAMES_ARE_IDS`: Set to True to use channel IDs instead of names (avoids rate limiting)

Required Slack scopes (see `scopes.txt`): `channels:history`, `channels:read`, `chat:write`, `mpim:write`, `users:read`, `groups:history`, `groups:write`

## Running the Bot

### Local execution
```bash
python src/main.py
```

### Docker
```bash
docker build -t pyslackrandomcoffee .
docker run --env-file .env pyslackrandomcoffee
```

### Testing
```bash
pytest test/test_pyslackrandomcoffee.py
```

## Core Architecture

The bot follows a linear workflow in `run_random_coffee()` (src/main.py:20):

1. **Configuration** (src/config.py): Loads and validates all required environment variables. Fails fast with clear errors if configuration is invalid.

2. **Channel Resolution** (src/slack_client.py `get_channels_id()`): Converts channel names to IDs via Slack API. Handles pagination to support large workspace channel lists. If `CHAN_NAMES_ARE_IDS=True`, skips this step.

3. **Bot Identity** (src/slack_client.py `get_bot_user_id()`): Retrieves bot's user ID to filter its own messages from history.

4. **Member Discovery** (src/slack_client.py `get_members_list()`): Fetches all non-bot members from the target channel. Handles pagination for channels with >1000 members. Returns user IDs.

5. **History Analysis** (src/pairing.py `parse_previous_pairs_from_metadata()`): Extracts previous pairs from Slack message metadata within `LOOKBACK_DAYS`. Only examines bot's own messages. Uses structured JSON metadata instead of text parsing.

6. **Pair Generation** (src/pairing.py `generate_pairs()`): Shuffles members and creates pairs while avoiding recent matches from history. Handles odd member counts by pairing one member twice. Uses previous matches to prefer new combinations.

7. **Messaging** (src/pairing.py and src/slack_client.py):
   - Sends group DMs to each pair
   - Posts pairs to memory channel with JSON metadata for future reference
   - If `PAIRS_ARE_PUBLIC=False`, notifies main channel without revealing pairs

### Key Implementation Details

- **Modular Architecture**: Code is split into 4 modules:
  - `config.py`: Configuration validation
  - `slack_client.py`: Slack API wrapper with error handling
  - `pairing.py`: Pairing logic and history management
  - `main.py`: Application orchestration
- **Error Handling**: Custom exceptions (`ConfigurationError`, `SlackClientError`, `PairingError`) with consistent error propagation
- **Type Safety**: Comprehensive type hints throughout codebase
- **Pagination**: All Slack API calls that return lists handle pagination (channels, members, history) to support large workspaces
- **Rate Limiting**: Configurable delays between paginated requests prevent API throttling (constants in slack_client.py)
- **Metadata Storage**: Previous pairs stored as structured JSON in Slack message metadata instead of fragile text parsing
- **Match Avoidance**: The pairing algorithm tries to find members who haven't been paired before, falling back to random selection when no new matches are possible

### Recent Changes

Based on git history:
- Enhanced user list pagination support for large workspaces (commit e8b2ec1)
- Changed from bulk workspace user requests to individual user API calls (commit a59a806)
- Reduced logging verbosity (commit 813f8fe)
