#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
request_manager.py - Gestionnaire de budget API journalier + cache enrichissement
"""

import os
import json
from datetime import datetime, timezone

UTC = timezone.utc


class RequestManager:
    def __init__(
        self,
        cache_dir="cache",
        state_file="request_state.json",
        enrich_file="enrichment_cache.json",
        daily_budget=80,
    ):
        self.cache_dir = cache_dir
        self.state_path = os.path.join(cache_dir, state_file)
        self.enrich_path = os.path.join(cache_dir, enrich_file)
        self.daily_budget = daily_budget

        os.makedirs(self.cache_dir, exist_ok=True)

        self.state = self._load_state()
        self.enrich_cache = self._load_enrich_cache()

    def _today_str(self):
        return str(datetime.now(UTC).date())

    def _load_json(self, path, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_state(self):
        data = self._load_json(self.state_path, {})
        if data.get("date") != self._today_str():
            return {"date": self._today_str(), "count": 0}
        return data

    def _load_enrich_cache(self):
        return self._load_json(self.enrich_path, {
            "predictions": {},
            "pregame": {},
            "team_results": {},
            "misc": {}
        })

    def save_state(self):
        self._save_json(self.state_path, self.state)

    def save_enrich_cache(self):
        self._save_json(self.enrich_path, self.enrich_cache)

    def can_request(self, count=1):
        return self.state.get("count", 0) + count <= self.daily_budget

    def consume(self, count=1):
        self.state["count"] = self.state.get("count", 0) + count
        self.save_state()

    def remaining(self):
        return max(0, self.daily_budget - self.state.get("count", 0))

    def get_cached(self, section: str, key: str):
        return self.enrich_cache.get(section, {}).get(str(key))

    def set_cached(self, section: str, key: str, data):
        self.enrich_cache.setdefault(section, {})
        self.enrich_cache[section][str(key)] = {
            "fetched_at": datetime.now(UTC).isoformat(),
            "data": data
        }
        self.save_enrich_cache()

    def clear_old_cache_section(self, section: str, keep_keys=None):
        keep_keys = set(keep_keys or [])
        if section not in self.enrich_cache:
            return
        self.enrich_cache[section] = {
            k: v for k, v in self.enrich_cache[section].items()
            if k in keep_keys
        }
        self.save_enrich_cache()