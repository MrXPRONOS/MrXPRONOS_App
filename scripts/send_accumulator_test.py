#!/usr/bin/env python3
"""Envoi unique du rendu accumulateur (document PNG non compressé) en canal TEST."""
import os
from pathlib import Path
import requests
from telegram_test_guard import validate_test_channel

def main():
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "").strip()
    file=Path(os.getenv("ACCUMULATOR_OUTPUT","telegram_out/accumulator_reference.png"))
    if not file.is_file() or file.stat().st_size<1000:
        raise SystemExit("Image accumulateur absente / invalide")
    verified=validate_test_channel(chat,token)
    with file.open("rb") as f:
        response=requests.post(
            "https://api.telegram.org/bot"+token+"/sendDocument",
            data={"chat_id":verified["chat_id"],"caption":"🧪 REPRODUCTION VISUELLE — 11 matchs de la capture de référence. Maquette de test, pas un ticket réel. Mr XPRONOS."},
            files={"document":("mrxpronos-combine-reference.png",f,"image/png")},
            timeout=(10,120),
        )
    response.raise_for_status()
    payload=response.json()
    if not payload.get("ok"):raise RuntimeError("Telegram a refusé le document")
    print("ACCUMULATOR_TEST_SENT message_id",payload["result"]["message_id"],"chat",verified["username"])
if __name__=="__main__":main()
