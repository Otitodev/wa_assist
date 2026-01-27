from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)

def should_pause_on_event(event: str, from_me: bool | None) -> bool:
    # Main collision rule:
    # If the owner sends a message (fromMe true) we pause the bot for that chat.
    if event == "messages.upsert" and from_me is True:
        return True
    # Some setups only deliver "messages.update" for fromMe; you can choose to pause on that too.
    # Keep it conservative:
    return False
