"""Recognition of the requested *public-channel message layout*.

Read-only: inspect public Telegram message metadata; never join, download, forward,
or infer that the underlying media has any particular copyright status.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from .matching import filename_of, is_video, is_mkv_document

@dataclass(frozen=True)
class PublicSequence:
    poster_id: int | None
    description_id: int | None
    video_id: int
    pattern: str

def _photo(message: Any) -> bool:
    return getattr(message, "photo", None) is not None

def _plain_text(message: Any) -> bool:
    return not _photo(message) and not getattr(message, "document", None) and not getattr(message, "video", None) and bool(str(getattr(message,"raw_text","") or "").strip())

def _meaningful(text: str) -> bool:
    import re
    content=re.sub(r"(?i)(?:https?://|www\.|t\.me/)\S+","",str(text or "")).strip()
    return len(content)>=14 and len(content.split())>=3

def _usable_media(message: Any) -> bool:
    return not getattr(message,"noforwards",False) and is_video(message)

def public_sequences(messages: Sequence[Any]) -> list[PublicSequence]:
    """Accept photo+caption->video and photo->text->video, MP4/MKV included.

    Preserve observed Telegram order (ID ascending). Only immediately adjacent
    messages count; replies to unrelated posts or newer posters break a sequence.
    Standalone named MKV files count separately as an explicit supported pattern.
    """
    ordered=sorted((m for m in messages if isinstance(getattr(m,"id",None),int)),key=lambda m:m.id)
    found: list[PublicSequence]=[]
    claimed:set[int]=set()
    for i,poster in enumerate(ordered):
        if not _photo(poster) or getattr(poster,"noforwards",False):
            continue
        nxt=ordered[i+1] if i+1<len(ordered) else None
        if not nxt:continue
        if _meaningful(getattr(poster,"raw_text","") or "") and _usable_media(nxt):
            if nxt.id not in claimed:
                found.append(PublicSequence(poster.id,None,nxt.id,"photo_caption_video"))
                claimed.add(nxt.id)
        elif _plain_text(nxt) and _meaningful(getattr(nxt,"raw_text","") or "") and i+2<len(ordered):
            mov=ordered[i+2]
            if _usable_media(mov) and mov.id not in claimed:
                found.append(PublicSequence(poster.id,nxt.id,mov.id,"photo_text_video"))
                claimed.add(mov.id)
    for msg in ordered:
        if msg.id in claimed or not _usable_media(msg) or not is_mkv_document(msg):
            continue
        file=filename_of(msg)
        if len(file.removesuffix(".mkv").strip("._- "))<5:
            continue
        found.append(PublicSequence(None,None,msg.id,"standalone_mkv"))
        claimed.add(msg.id)
    return found

def assess_public_channel(messages:Sequence[Any], min_examples:int=2)->dict:
    found=public_sequences(messages)
    patterns=sorted({p.pattern for p in found})
    return {
        "format_verified":len(found)>=min_examples,
        "matching_pairs":len(found),
        "patterns":patterns,
        "sample_post_ids":[p.poster_id if p.poster_id is not None else p.video_id for p in found[:3]],
        "verification_method":"public_message_structure",
    }
