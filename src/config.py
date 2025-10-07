#!/usr/bin/env python
"""Configuration management and validation for pyslackrandomcoffee."""

import os
import sys
import logging
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass
class Config:
    """Application configuration."""
    slack_token: str
    channel_name: str
    private_channel_name: str
    pairs_are_public: bool
    chan_names_are_ids: bool
    lookback_days: int
    magical_text: str

    @classmethod
    def from_env(cls) -> 'Config':
        """Load and validate configuration from environment variables.

        Returns:
            Config: Validated configuration object.

        Raises:
            ConfigurationError: If required configuration is missing or invalid.
        """
        # Load .env file
        load_dotenv(find_dotenv())

        # Required variables
        slack_token = os.getenv('SLACK_API_TOKEN')
        if not slack_token:
            raise ConfigurationError("SLACK_API_TOKEN environment variable is required")

        channel_name = os.getenv('CHANNEL_NAME')
        if not channel_name:
            raise ConfigurationError("CHANNEL_NAME environment variable is required")

        lookback_days_str = os.getenv('LOOKBACK_DAYS')
        if not lookback_days_str:
            raise ConfigurationError("LOOKBACK_DAYS environment variable is required")

        try:
            lookback_days = int(lookback_days_str)
            if lookback_days < 1:
                raise ValueError("LOOKBACK_DAYS must be positive")
        except ValueError as e:
            raise ConfigurationError(f"LOOKBACK_DAYS must be a positive integer: {e}")

        magical_text = os.getenv('MAGICAL_TEXT')
        if not magical_text:
            raise ConfigurationError("MAGICAL_TEXT environment variable is required")

        # Optional variables with defaults
        private_channel_name = os.getenv('PRIVATE_CHANNEL_NAME_FOR_MEMORY', 'randomcoffebotprivatechannelformemory')
        pairs_are_public = os.getenv("PAIRS_ARE_PUBLIC", 'False').lower() in ('true', 't', 'yes', 'y', '1')
        chan_names_are_ids = os.getenv("CHAN_NAMES_ARE_IDS", 'False').lower() in ('true', 't', 'yes', 'y', '1')

        logging.info(f"Configuration loaded: channel={channel_name}, lookback_days={lookback_days}")

        return cls(
            slack_token=slack_token,
            channel_name=channel_name,
            private_channel_name=private_channel_name,
            pairs_are_public=pairs_are_public,
            chan_names_are_ids=chan_names_are_ids,
            lookback_days=lookback_days,
            magical_text=magical_text
        )
