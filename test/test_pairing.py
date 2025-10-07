#!/usr/bin/env python
"""Tests for pairing module."""

import sys
import os
from collections import Counter

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pairing import generate_pairs, parse_previous_pairs_from_metadata, pairs_to_metadata


def test_generate_pairs():
    """Test pair generation with various scenarios."""

    def helper(members, number_of_pairs, expected_max_occurrences, previous_pairs):
        pairs = generate_pairs(members.copy(), previous_pairs)
        unpacked_members = [name for pair in pairs for name in pair]

        # Ensure all member names are used in the pairs
        assert set(unpacked_members) == set(members), f"Not all members used: {unpacked_members} vs {members}"

        # Ensure that we get the correct number of pairs
        assert len(pairs) == number_of_pairs, f"Expected {number_of_pairs} pairs, got {len(pairs)}"

        # Count the occurrences of names in the unpacked_members list
        if expected_max_occurrences:
            counter = Counter(unpacked_members)
            max_occurrences = max(list(counter.values()))
            assert max_occurrences == expected_max_occurrences, \
                f"Expected max {expected_max_occurrences} occurrences, got {max_occurrences}"

    # Uneven number of members
    helper(['Liam', 'Olivia', 'Noah', 'Emma', 'Ava'], 3, 2, None)

    # Even number of members
    helper(['Liam', 'Olivia', 'Noah', 'Emma', 'Ava', 'Sophia'], 3, 1, None)

    # A single member pair with one-self
    helper(['Liam'], 1, 2, None)

    # No members found
    helper([], 0, 0, None)

    # Even with previous matches
    helper(['Liam', 'Olivia', 'Noah', 'Emma', 'Ava', 'Sophia'], 3, 1,
           [[('Olivia', 'Noah'), ('Olivia', 'Ava')]])

    # Uneven with previous matches
    helper(['Liam', 'Olivia', 'Emma', 'Ava', 'Sophia'], 3, 2,
           [[('Olivia', 'Noah'), ('Olivia', 'Ava')]])


def test_metadata_roundtrip():
    """Test converting pairs to metadata and parsing back."""
    original_pairs = [('U123', 'U456'), ('U789', 'U012')]

    # Convert to metadata
    metadata = pairs_to_metadata(original_pairs)

    # Simulate a Slack message with this metadata
    messages = [{
        'metadata': {
            'event_type': 'random_coffee_pairs',
            'event_payload': metadata
        }
    }]

    # Parse back
    parsed = parse_previous_pairs_from_metadata(messages)

    assert parsed is not None
    assert len(parsed) == 1
    assert parsed[0] == original_pairs


def test_parse_multiple_history():
    """Test parsing multiple rounds of pairs from history."""
    messages = [
        {
            'metadata': {
                'event_type': 'random_coffee_pairs',
                'event_payload': {
                    'pairs': [
                        {'user1': 'U1', 'user2': 'U2'},
                        {'user1': 'U3', 'user2': 'U4'}
                    ]
                }
            }
        },
        {
            'metadata': {
                'event_type': 'random_coffee_pairs',
                'event_payload': {
                    'pairs': [
                        {'user1': 'U1', 'user2': 'U3'},
                        {'user1': 'U2', 'user2': 'U4'}
                    ]
                }
            }
        },
        {
            'text': 'Regular message without metadata'
        }
    ]

    parsed = parse_previous_pairs_from_metadata(messages)

    assert parsed is not None
    assert len(parsed) == 2
    assert parsed[0] == [('U1', 'U2'), ('U3', 'U4')]
    assert parsed[1] == [('U1', 'U3'), ('U2', 'U4')]


def test_parse_no_metadata():
    """Test parsing when no metadata exists."""
    messages = [
        {'text': 'Just a regular message'},
        {'text': 'Another message'}
    ]

    parsed = parse_previous_pairs_from_metadata(messages)
    assert parsed is None


if __name__ == '__main__':
    test_generate_pairs()
    test_metadata_roundtrip()
    test_parse_multiple_history()
    test_parse_no_metadata()
    print("All tests passed!")
