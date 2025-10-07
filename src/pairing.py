#!/usr/bin/env python
"""Pairing logic and history management for random coffee matches."""

import random
import logging
import datetime
import json
from typing import List, Tuple, Dict, Optional, Set


PairList = List[Tuple[str, str]]
PairHistory = List[PairList]


class PairingError(Exception):
    """Raised when pairing operations fail."""
    pass


def parse_previous_pairs_from_metadata(messages: List[Dict]) -> Optional[PairHistory]:
    """Extract previous pairs from message metadata.

    Args:
        messages: List of message dictionaries from Slack API.

    Returns:
        List of pair lists, or None if no pairs found.
    """
    previous_pairs = []

    for message in messages:
        metadata = message.get('metadata')
        if not metadata:
            logging.info(f"No metadata in message: {json.dumps(message)}")
            continue

        logging.info(f"Reading metadata: {json.dumps(metadata)}")
        # Check if this is a random coffee pairs message
        if metadata.get('event_type') != 'random_coffee_pairs':
            continue

        event_payload = metadata.get('event_payload', {})
        pairs_data = event_payload.get('pairs', [])

        # Convert from list of dicts to list of tuples
        if pairs_data:
            pair_list = [(pair['user1'], pair['user2']) for pair in pairs_data]
            previous_pairs.append(pair_list)

    if not previous_pairs:
        return None

    logging.info(f"Extracted {len(previous_pairs)} previous pair sets from metadata")
    return previous_pairs


def build_previous_matches_dict(members: List[str], previous_pairs: Optional[PairHistory]) -> Dict[str, Set[str]]:
    """Build a dictionary of previous matches for each member.

    Args:
        members: List of member identifiers.
        previous_pairs: Historical pair data.

    Returns:
        Dictionary mapping each member to set of previous matches.
    """
    members_previous_matches: Dict[str, Set[str]] = {member: set() for member in members}

    if not previous_pairs:
        return members_previous_matches

    for member in members:
        for pair_set in previous_pairs:
            for p1, p2 in pair_set:
                if p1 == member:
                    members_previous_matches[member].add(p2)
                elif p2 == member:
                    members_previous_matches[member].add(p1)

    return members_previous_matches


def find_best_match(
    member1: str,
    available_members: List[str],
    members_previous_matches: Dict[str, Set[str]]
) -> str:
    """Find the best match for member1 from available members.

    Prefers members who haven't been matched before, falls back to random.

    Args:
        member1: Member to match.
        available_members: List of available members to match with.
        members_previous_matches: Dictionary of previous matches.

    Returns:
        The chosen match.

    Raises:
        PairingError: If no available members.
    """
    if not available_members:
        raise PairingError(f"No available members to match with {member1}")

    # Try to find someone who hasn't been matched before
    new_candidates = [
        member for member in available_members
        if member not in members_previous_matches[member1]
    ]

    if new_candidates:
        return random.choice(new_candidates)
    else:
        # All available members have been matched before, pick randomly
        return random.choice(available_members)


def generate_pairs(members: List[str], previous_pairs: Optional[PairHistory] = None) -> PairList:
    """Generate random pairs from members, avoiding recent matches.

    If there's an odd number of members, one member will be matched twice.

    Args:
        members: List of member identifiers.
        previous_pairs: Historical pair data to avoid repeating.

    Returns:
        List of tuples representing pairs.

    Raises:
        PairingError: If pairing fails.
    """
    if not members:
        return []

    # Make a copy to avoid modifying the original
    available = members.copy()
    random.shuffle(available)

    # Build previous matches lookup
    members_previous_matches = build_previous_matches_dict(members, previous_pairs)

    pairs = []
    first_member = available[-1]  # Remember first member for odd case

    while available:
        if len(available) >= 2:
            # Normal case: pair two available members
            member1 = available.pop()
            member2 = find_best_match(member1, available, members_previous_matches)
            available.remove(member2)
            pairs.append((member1, member2))
        else:
            # Odd case: pair last member with first member
            member2 = find_best_match(first_member, available, members_previous_matches)
            available.remove(member2)
            pairs.append((first_member, member2))

    logging.info(f"Generated {len(pairs)} pairs")
    return pairs


def format_pairs_message(
    pairs: PairList,
    magical_text: str,
    lookback_days: int
) -> str:
    """Format pairs into a Slack message.

    Args:
        pairs: List of member pairs.
        magical_text: Header text for the message.
        lookback_days: Number of days considered in history.

    Returns:
        Formatted message string.
    """
    if not pairs:
        return ""

    header = f"{magical_text}:\n"
    pair_lines = [f" {i+1}. <@{p1}> and <@{p2}>\n" for i, (p1, p2) in enumerate(pairs)]
    footer = (
        f"An uneven number of members results in one person getting two coffee matches. "
        f"Matches from the last {lookback_days} days considered to avoid matching the "
        f"same members several times in the time period."
    )

    return header + ''.join(pair_lines) + footer


def pairs_to_metadata(pairs: PairList) -> Dict:
    """Convert pairs to metadata format for Slack.

    Args:
        pairs: List of member pairs.

    Returns:
        Dictionary formatted for Slack message metadata.
    """
    return {
        "pairs": [
            {"user1": p1, "user2": p2}
            for p1, p2 in pairs
        ],
        "timestamp": datetime.datetime.now().isoformat(),
        "count": len(pairs)
    }


def send_pair_notifications(
    pairs: PairList,
    channel_id: str,
    slack_client
) -> None:
    """Send group DMs to all pairs.

    Args:
        pairs: List of member pairs.
        channel_id: Channel ID for reference in message.
        slack_client: SlackClient instance.

    Raises:
        PairingError: If notifications fail.
    """
    success_count = 0
    fail_count = 0

    for pair in pairs:
        try:
            message = (
                f"Hello <@{pair[0]}> and <@{pair[1]}>\n"
                f"You've been randomly selected for <#{channel_id}>!\n"
                f"Take some time to meet soon."
            )
            slack_client.send_group_dm(pair, message)
            success_count += 1
        except Exception as e:
            logging.error(f"Failed to send DM to {pair}: {e}")
            fail_count += 1

    logging.info(f"Sent {success_count} group DMs, {fail_count} failed")

    if fail_count > 0 and success_count == 0:
        raise PairingError(f"Failed to send all {fail_count} group DMs")
