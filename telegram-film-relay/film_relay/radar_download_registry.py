"""Register verified central Telegram media with CineRadar's existing delivery bot.

The existing cine_classic_links / cine_classic_deliveries workflow handles
single-file delivery for any CineX category through Telegram copyMessage.
No video bytes flow through Cloudflare. Never log tokens.
"""
from __future__ import annotations

import logging
import os
import re
import secrets

import requests

LOG = logging.getLogger("cinex.radar_registry")
CHANNEL = re.compile(r"^-100[0-9]{5,}$")
BOT_URL = re.compile(r"^https://t\.me/CineRadarFr_Bot\?start=d_[A-Za-z0-9_-]{24}$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{24}$")
ACCOUNT = re.compile(r"^[a-f0-9]{32}$")
DB_ID = re.compile(r"^[a-f0-9-]{36}$")
HANDLE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")

DEFAULT_ACCOUNT = "9c86118191b804d91b5f5b2c89114999"
DEFAULT_DATABASE = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"


def is_bot_download_url(url: str) -> bool:
    return bool(BOT_URL.fullmatch(str(url or "")))


class RadarDailyQuotaError(RuntimeError):
    """D1 free-tier row-read limit (Cloudflare code 7500), retry next UTC day."""


class RadarRegistry:
    def __init__(self, *, env=None, session=None):
        self.env = env if env is not None else os.environ
        self.session = session if session is not None else requests
        self.token = str(self.env.get("CLOUDFLARE_API_TOKEN") or
                         self.env.get("CF_API_TOKEN") or "").strip()
        self.account = str(self.env.get("CLOUDFLARE_ACCOUNT_ID") or DEFAULT_ACCOUNT)
        self.database = str(self.env.get("CINERADAR_D1_DATABASE_ID") or DEFAULT_DATABASE)
        if not ACCOUNT.fullmatch(self.account) or not DB_ID.fullmatch(self.database):
            raise ValueError("Identifiants du registre CineRadar D1 invalides.")

    def _query(self, sql, params=()):
        if not self.token:
            raise RuntimeError("Token Cloudflare manquant : téléchargement CinéRadar non activé.")
        url = ("https://api.cloudflare.com/client/v4/accounts/" + self.account
               + "/d1/database/" + self.database + "/query")
        try:
            response = self.session.post(
                url,
                headers={"Authorization": "Bearer " + self.token,
                         "Content-Type": "application/json"},
                json={"sql": sql, "params": list(params)},
                timeout=12,
            )
            payload = response.json()
            errors = payload.get("errors") or []
            if any(str(item.get("code")) == "7500"
                   for item in errors if isinstance(item, dict)):
                raise RadarDailyQuotaError(
                    "CineRadar D1 : limite quotidienne de lectures atteinte (7500).")
            if (not response.ok or not payload.get("success")
                    or not payload.get("result")
                    or not payload["result"][0].get("success", False)):
                raise RuntimeError("CineRadar D1 a refusé l'enregistrement.")
            return payload["result"][0]
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("Registre CineRadar D1 indisponible.") from exc

    def register(self, *, private_channel: int, message_id: int,
                 title: str, public_handle: str) -> str:
        if (not CHANNEL.fullmatch(str(private_channel))
                or not isinstance(message_id, int) or message_id <= 0
                or not HANDLE.fullmatch(str(public_handle))):
            raise ValueError("Données Telegram du téléchargement invalides.")
        description = " ".join(str(title or "").split())[:180]
        if len(description) < 3:
            raise ValueError("Titre de téléchargement vide.")
        # Bot delivery copies only from the owner-verified stock channel.
        # A Telegram user session being able to upload is not proof that the
        # CineRadar bot can copy its media. Fail closed on a different channel.
        stock = self._query(
            "SELECT stock_chat_id,radar_bot_id FROM cine_private_stock_config "
            "WHERE singleton=1 AND ready=1 LIMIT 1"
        ).get("results") or []
        if (len(stock) != 1 or str(stock[0].get("stock_chat_id")) != str(private_channel)
                or int(stock[0].get("radar_bot_id") or 0) <= 0):
            raise RuntimeError(
                "Le canal central ne correspond pas au stock privé vérifié du bot CineRadar.")
        gate = self._query(
            "SELECT value FROM bot_settings "
            "WHERE setting_key='cine_delivery_enabled' LIMIT 1"
        ).get("results") or []
        if len(gate) != 1 or str(gate[0].get("value")) != "1":
            raise RuntimeError("Téléchargements CineRadar désactivés.")
        existing = self._query(
            "SELECT token,status FROM cine_classic_links "
            "WHERE source_chat_id=? AND source_message_id=? LIMIT 1",
            (str(private_channel), message_id),
        ).get("results") or []
        if existing:
            item = existing[0]
            if item.get("status") != "published" or not TOKEN.fullmatch(str(item.get("token", ""))):
                raise RuntimeError("Vidéo déjà enregistrée mais non publiée ou suspendue.")
            return "https://t.me/CineRadarFr_Bot?start=d_" + item["token"]

        # 144-bit random token. Unique document mapping also blocks duplicates.
        candidate = secrets.token_urlsafe(18)
        if not TOKEN.fullmatch(candidate):
            raise RuntimeError("Identifiant de téléchargement invalide.")
        self._query(
            "INSERT OR IGNORE INTO cine_classic_links"
            "(token,source_chat_id,source_message_id,title,public_handle,status)"
            " VALUES(?,?,?,?,?,'published')",
            (candidate, str(private_channel), message_id, description, public_handle),
        )
        receipt = self._query(
            "SELECT token,status FROM cine_classic_links "
            "WHERE source_chat_id=? AND source_message_id=? LIMIT 1",
            (str(private_channel), message_id),
        ).get("results") or []
        if (len(receipt) != 1 or receipt[0].get("status") != "published"
                or not TOKEN.fullmatch(str(receipt[0].get("token", "")))):
            raise RuntimeError("Aucun reçu de téléchargement CineRadar vérifié.")
        LOG.info("CineRadar : copie privée enregistrée pour livraison Telegram.")
        return "https://t.me/CineRadarFr_Bot?start=d_" + receipt[0]["token"]
