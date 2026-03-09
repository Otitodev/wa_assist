"""
Tests for collision detection logic.
"""
import pytest
from app.services.collision import should_pause_on_event


def test_pause_on_messages_upsert_from_me():
    assert should_pause_on_event("messages.upsert", True) is True


def test_no_pause_on_messages_upsert_not_from_me():
    assert should_pause_on_event("messages.upsert", False) is False


def test_no_pause_on_messages_upsert_none():
    assert should_pause_on_event("messages.upsert", None) is False


def test_no_pause_on_other_events():
    assert should_pause_on_event("messages.update", True) is False
    assert should_pause_on_event("connection.update", True) is False
    assert should_pause_on_event("qrcode.updated", True) is False
