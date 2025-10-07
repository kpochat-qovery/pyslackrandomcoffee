#!/usr/bin/env python
"""Slack API client wrapper with improved error handling."""

import time
import json
import logging
from typing import Optional, List, Dict, Tuple
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClientError(Exception):
    """Raised when Slack API operations fail."""
    pass


# Rate limiting delays (in seconds)
CHANNEL_LIST_DELAY = 10
HISTORY_PAGE_DELAY = 1
MEMBERS_PAGE_DELAY = 5
MPIM_DELAY = 1


class SlackClient:
    """Wrapper around Slack WebClient with retry logic and error handling."""

    def __init__(self, token: str):
        """Initialize Slack client.

        Args:
            token: Slack API token.

        Raises:
            SlackClientError: If token is invalid or connection fails.
        """
        if not token:
            raise SlackClientError("Slack token cannot be empty")

        self.client = WebClient(token=token)
        self._bot_user_id: Optional[str] = None

    def get_bot_user_id(self) -> str:
        """Get the bot's user ID.

        Returns:
            Bot user ID.

        Raises:
            SlackClientError: If unable to authenticate.
        """
        if self._bot_user_id:
            return self._bot_user_id

        try:
            test = self.client.auth_test()
            self._bot_user_id = test["user_id"]
            logging.info(f"Bot user ID: {self._bot_user_id}")
            return self._bot_user_id
        except SlackApiError as e:
            raise SlackClientError(f"Failed to get bot user ID: {e}")

    def get_channels_id(self, channels: List[str], chan_names_are_ids: bool) -> Dict[str, str]:
        """Convert channel names to IDs.

        Args:
            channels: List of channel names.
            chan_names_are_ids: If True, treat channel names as IDs.

        Returns:
            Dictionary mapping channel names to IDs.

        Raises:
            SlackClientError: If unable to resolve channel IDs.
        """
        if chan_names_are_ids:
            return {chan: chan for chan in channels}

        chan_name_to_id = {chan: None for chan in channels}

        try:
            has_more = True
            next_cursor = None
            while has_more:
                response = self.client.conversations_list(
                    limit=200,
                    cursor=next_cursor,
                    types='public_channel,private_channel'
                )
                channel_list = response["channels"]
                logging.info(f"Retrieved {len(channel_list)} channels")

                for c in channel_list:
                    if c.get('name') in chan_name_to_id.keys():
                        chan_name_to_id[c.get('name')] = c['id']

                # Check if we found all channels
                if None not in chan_name_to_id.values():
                    break

                has_more = (response.get('response_metadata') is not None and
                           response['response_metadata'].get('next_cursor'))
                if has_more:
                    next_cursor = response['response_metadata']['next_cursor']
                    logging.info(f"Currently retrieved: {chan_name_to_id}")
                    time.sleep(CHANNEL_LIST_DELAY)

            # Check if any channels weren't found
            missing = [name for name, id in chan_name_to_id.items() if id is None]
            if missing:
                raise SlackClientError(f"Could not find channels: {missing}")

            return chan_name_to_id

        except SlackApiError as e:
            raise SlackClientError(f"Error getting channel IDs for {channels}: {e}")

    def get_members_list(self, channel_id: str) -> List[str]:
        """Get list of non-bot members in a channel.

        Args:
            channel_id: Slack channel ID.

        Returns:
            List of user IDs.

        Raises:
            SlackClientError: If unable to fetch members.
        """
        try:
            # Get member IDs with pagination
            member_ids = []
            has_more = True
            next_cursor = None

            while has_more:
                response = self.client.conversations_members(
                    limit=200,
                    channel=channel_id,
                    cursor=next_cursor
                )
                member_ids.extend(response['members'])

                has_more = (response.get('response_metadata') is not None and
                           response['response_metadata'].get('next_cursor'))
                if has_more:
                    next_cursor = response['response_metadata']['next_cursor']
                    logging.info(f"Currently retrieved: {len(member_ids)} members")
                    time.sleep(MEMBERS_PAGE_DELAY)

            # Fetch user info and filter bots
            members = []
            for member_id in member_ids:
                try:
                    user = self.client.users_info(user=member_id)['user']
                    if not user.get('is_bot', False):
                        members.append(user['id'])
                except SlackApiError as e:
                    logging.warning(f"Could not fetch user info for {member_id}: {e}")
                    continue

            logging.info(f"Found {len(members)} non-bot members")
            return members

        except SlackApiError as e:
            raise SlackClientError(f"Error getting members for channel {channel_id}: {e}")

    def get_conversation_history(
        self,
        channel_id: str,
        oldest_timestamp: float,
        newest_timestamp: float,
        bot_user_id: Optional[str] = None,
        max_messages: Optional[int] = None
    ) -> List[Dict]:
        """Fetch conversation history with pagination.

        Args:
            channel_id: Slack channel ID.
            oldest_timestamp: Unix timestamp for oldest message.
            newest_timestamp: Unix timestamp for newest message.
            bot_user_id: If provided, only return messages from this user.
            max_messages: Maximum number of messages to return.

        Returns:
            List of message dictionaries.

        Raises:
            SlackClientError: If unable to fetch history.
        """
        try:
            params = {
                'channel': channel_id,
                'limit': 200,
                'oldest': oldest_timestamp,
                'newest': newest_timestamp,
                'include_all_metadata': True
            }

            conversation_history = []
            has_more = True
            next_cursor = None

            while has_more:
                response = self.client.conversations_history(**params, cursor=next_cursor)
                conversation_history.extend(response["messages"])

                has_more = response.get('has_more', False)
                if has_more:
                    next_cursor = response['response_metadata']['next_cursor']
                    logging.info('Fetching next page of conversation history')
                    time.sleep(HISTORY_PAGE_DELAY)

            logging.info(f"Retrieved {len(conversation_history)} total messages")

            # Filter by bot user if specified
            if bot_user_id:
                conversation_history = [
                    msg for msg in conversation_history
                    if msg.get("user") == bot_user_id
                ]
                logging.info(f"Filtered to {len(conversation_history)} messages from bot")

            # Limit messages if specified
            if max_messages:
                conversation_history = conversation_history[:max_messages]

            return conversation_history

        except SlackApiError as e:
            raise SlackClientError(f"Error getting conversation history for {channel_id}: {e}")

    def post_message(self, message: str, channel_id: str) -> bool:
        """Send a text message to a channel.

        Args:
            message: Message text.
            channel_id: Channel or user ID.

        Returns:
            True if successful.

        Raises:
            SlackClientError: If message fails to send.
        """
        try:
            response = self.client.chat_postMessage(channel=channel_id, text=message)
            if not response.get('ok', False):
                raise SlackClientError(f"Message not OK: {response}")
            return True
        except SlackApiError as e:
            raise SlackClientError(f"Error posting message to {channel_id}: {e}")

    def post_message_with_metadata(
        self,
        message: str,
        channel_id: str,
        metadata: Dict
    ) -> bool:
        """Send a message with JSON metadata attached.

        Args:
            message: Message text.
            channel_id: Channel or user ID.
            metadata: Dictionary to attach as metadata.

        Returns:
            True if successful.

        Raises:
            SlackClientError: If message fails to send.
        """
        try:
            # Slack metadata format requires event_type and event_payload
            metadata_formatted = {
                "event_type": "random_coffee_pairs",
                "event_payload": metadata
            }

            response = self.client.chat_postMessage(
                channel=channel_id,
                text=message,
                metadata=metadata_formatted
            )
            if not response.get('ok', False):
                raise SlackClientError(f"Message not OK: {response}")
            return True
        except SlackApiError as e:
            raise SlackClientError(f"Error posting message with metadata to {channel_id}: {e}")

    def send_group_dm(self, user_ids: Tuple[str, str], message: str) -> bool:
        """Send a group DM to a pair of users.

        Args:
            user_ids: Tuple of two user IDs.
            message: Message text.

        Returns:
            True if successful.

        Raises:
            SlackClientError: If DM fails to send.
        """
        try:
            mpim = self.client.conversations_open(users=user_ids)
            self.post_message(message, mpim["channel"]["id"])
            time.sleep(MPIM_DELAY)
            return True
        except SlackApiError as e:
            raise SlackClientError(f"Error sending group DM to {user_ids}: {e}")
