#!/usr/bin/env python
"""Main entry point for pyslackrandomcoffee bot."""

import sys
import logging
import datetime
from typing import Optional

from config import Config, ConfigurationError
from slack_client import SlackClient, SlackClientError
from pairing import (
    parse_previous_pairs_from_metadata,
    generate_pairs,
    format_pairs_message,
    pairs_to_metadata,
    send_pair_notifications,
    PairingError
)


def run_random_coffee(config: Optional[Config] = None) -> None:
    """Execute random coffee pairing and notifications.

    Args:
        config: Configuration object. If None, loads from environment.

    Raises:
        ConfigurationError: If configuration is invalid.
        SlackClientError: If Slack API operations fail.
        PairingError: If pairing or notifications fail.
    """
    # Load configuration
    if config is None:
        config = Config.from_env()

    # Use the configured channel
    channel = config.channel_name
    logging.info(f"Using channel: {channel}")

    # Determine memory channel (where pair history is stored)
    if config.pairs_are_public:
        memory_channel = channel
        channels_to_resolve = [channel]
    else:
        memory_channel = config.private_channel_name
        channels_to_resolve = [channel, memory_channel]

    # Initialize Slack client
    try:
        slack_client = SlackClient(config.slack_token)
    except SlackClientError as e:
        logging.error(f"Failed to initialize Slack client: {e}")
        raise

    # Resolve channel IDs
    try:
        channel_ids = slack_client.get_channels_id(channels_to_resolve, config.chan_names_are_ids)
        channel_id = channel_ids[channel]
        memory_channel_id = channel_ids[memory_channel]
        logging.info(f"Resolved channel IDs: {channel_ids}")
    except SlackClientError as e:
        logging.error(f"Failed to resolve channel IDs: {e}")
        raise

    # Get bot user ID
    try:
        bot_user_id = slack_client.get_bot_user_id()
    except SlackClientError as e:
        logging.error(f"Failed to get bot user ID: {e}")
        raise

    # Get channel members
    try:
        members = slack_client.get_members_list(channel_id)
        logging.info(f"Found {len(members)} members in channel")
    except SlackClientError as e:
        logging.error(f"Failed to get channel members: {e}")
        raise

    if not members:
        logging.warning("No members found in channel, nothing to do")
        return

    # Get conversation history to find previous pairs
    try:
        oldest_timestamp = (
            datetime.datetime.today() - datetime.timedelta(days=config.lookback_days)
        ).timestamp()
        newest_timestamp = datetime.datetime.now().timestamp()

        messages = slack_client.get_conversation_history(
            channel_id=memory_channel_id,
            oldest_timestamp=oldest_timestamp,
            newest_timestamp=newest_timestamp,
            bot_user_id=bot_user_id,
            max_messages=len(members) - 2
        )

        previous_pairs = parse_previous_pairs_from_metadata(messages)
        if previous_pairs:
            logging.info(f"Found {len(previous_pairs)} previous pairing rounds")
        else:
            logging.info("No previous pairs found in history")

    except SlackClientError as e:
        logging.error(f"Failed to get conversation history: {e}")
        raise

    # Generate pairs
    try:
        pairs = generate_pairs(members, previous_pairs)
        logging.info(f"Generated {len(pairs)} pairs")
    except PairingError as e:
        logging.error(f"Failed to generate pairs: {e}")
        raise

    if not pairs:
        logging.warning("No pairs generated, nothing to do")
        return

    # Send group DMs to pairs
    try:
        send_pair_notifications(pairs, channel_id, slack_client)
    except PairingError as e:
        logging.warning(f"Some notifications failed: {e}")
        # Continue anyway to post the pairs

    # Post pairs to memory channel with metadata
    try:
        message = format_pairs_message(pairs, config.magical_text, config.lookback_days)
        metadata = pairs_to_metadata(pairs)

        slack_client.post_message_with_metadata(message, memory_channel_id, metadata)
        logging.info(f"Posted pairs to memory channel: {memory_channel}")

        # If pairs are not public, notify main channel
        if not config.pairs_are_public:
            notification = f"I just launched a new round of {len(pairs)} pairs! Check your DMs."
            slack_client.post_message(notification, channel_id)
            logging.info(f"Posted notification to main channel: {channel}")

    except SlackClientError as e:
        logging.error(f"Failed to post pairs: {e}")
        raise

    logging.info("Random coffee pairing completed successfully")


def main():
    """Main entry point with error handling."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        run_random_coffee()
        sys.exit(0)
    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except SlackClientError as e:
        logging.error(f"Slack API error: {e}")
        sys.exit(2)
    except PairingError as e:
        logging.error(f"Pairing error: {e}")
        sys.exit(3)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(99)


if __name__ == '__main__':
    main()
