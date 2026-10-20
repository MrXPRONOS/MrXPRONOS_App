"""Idempotent Telegram message edits for catalogue indexes."""
from __future__ import annotations

from telethon.errors import MessageNotModifiedError


async def edit_message_if_changed(client, peer, message_id: int, text: str, **kwargs) -> bool:
    """Return False for an unchanged Telegram message instead of failing a run.

    This is safe when recovering a partial catalogue checkpoint: the target
    already contains exactly the intended text.
    """
    try:
        await client.edit_message(peer, message_id, text, **kwargs)
    except MessageNotModifiedError:
        return False
    return True
