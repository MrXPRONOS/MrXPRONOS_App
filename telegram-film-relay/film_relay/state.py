"""JSON persistence for GitHub Actions (committed at the end of each run)."""
from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, path: str):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {}
        self.data.setdefault("last_seen", {})
        self.data.setdefault("processed", {})
        self.data.setdefault("videos", {})
        self.data.setdefault("staged", {})

    def recorded(self, pair_id: str, media_id: str | None) -> bool:
        return pair_id in self.data["processed"] or bool(media_id and media_id in self.data["videos"])

    def add(self, pair_id: str, media_id: str | None, private_id: int, public_id: int) -> None:
        entry = {"private_message_id": private_id, "public_message_id": public_id}
        self.data["processed"][pair_id] = entry
        self.data["staged"].pop(pair_id, None)
        if media_id:
            self.data["videos"][media_id] = pair_id
        self.save()

    def get_staged_posts(self, pair_id: str) -> dict[str, int]:
        """Return partial private posts; supports older numeric video-only stages."""
        result = self.data["staged"].get(pair_id)
        if result is None:
            return {}
        if isinstance(result, dict):
            return {k: int(v) for k, v in result.items() if k in ("poster", "video") and v is not None}
        return {"video": int(result)}

    def get_stage(self, pair_id: str) -> int | None:
        """Compatibility with the original state interface (video ID)."""
        return self.get_staged_posts(pair_id).get("video")

    def stage_poster(self, pair_id: str, private_id: int) -> None:
        current = self.get_staged_posts(pair_id)
        current["poster"] = int(private_id)
        self.data["staged"][pair_id] = current
        self.save()

    def stage(self, pair_id: str, private_id: int) -> None:
        current = self.get_staged_posts(pair_id)
        current["video"] = int(private_id)
        self.data["staged"][pair_id] = current
        self.save()

    def seen(self, source: str) -> int:
        return int(self.data["last_seen"].get(source, 0))

    def advance(self, source: str, message_id: int) -> None:
        self.data["last_seen"][source] = max(self.seen(source), message_id)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)
