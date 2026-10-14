#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

from football_channel import Publication, Sender
from generic_football_content import banner_caption

LOGO_A="https://r2.thesportsdb.com/images/media/team/badge/jcgrml1756649030.png"
LOGO_B="https://r2.thesportsdb.com/images/media/team/badge/tprtus1448813498.png"

def marked(text: str, label: str) -> str:
    rows=text.split("\n",1)
    marker=f"<i>🧪 TEST CANAL • {label}</i>"
    return rows[0]+"\n"+marker+(("\n"+rows[1]) if len(rows)>1 else "")

def main() -> None:
    # Safety: this test must never silently fall back to production.
    expected=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "").strip()
    actual=(os.getenv("FOOTBALL_NEWS_CHAT_ID") or "").strip()
    if not expected or actual != expected:
        raise RuntimeError("Le test complet est autorisé uniquement sur TELEGRAM_TEST_CHAT_ID")
    os.environ["FOOTBALL_REQUIRE_COMMENTS"]="0"
    sender=Sender(dry_run=False)
    day=datetime.now(timezone.utc).strftime("%d/%m/%Y")
    players_a=["R. Martin","A. Diallo","M. Koffi","J. Mensah","D. Silva","Y. Traoré","N. Lopez","A. Mensima","K. Barry","S. Costa","I. Toure"]
    players_b=["P. Rossi","L. Koné","A. Santos","M. Camara","T. Diallo","J. Silva","A. Mensah","R. Koffi","M. Barry","F. Lopez","E. Traoré"]

    items=[
      Publication("programme","test:template:programme",
        marked("<b>📅 MATCHS DU JOUR</b>\nLes affiches à suivre aujourd’hui.","PREMIUM 1/4"),
        card={"day":day,"matches":[
          {"home":"Arsenal","away":"Chelsea","time":"17h30","league":"Premier League","home_logo":LOGO_A,"away_logo":LOGO_B},
          {"home":"Real Madrid","away":"Barcelona","time":"19h00","league":"Liga","home_logo":LOGO_A,"away_logo":LOGO_B},
          {"home":"Liverpool","away":"Roma","time":"20h00","league":"Europe","home_logo":LOGO_A,"away_logo":LOGO_B},
          {"home":"PSG","away":"Marseille","time":"20h45","league":"Ligue 1","home_logo":LOGO_A,"away_logo":LOGO_B},
          {"home":"Bayern","away":"Dortmund","time":"21h00","league":"Bundesliga","home_logo":LOGO_A,"away_logo":LOGO_B},
        ]}),
      Publication("avant_match","test:template:avant",
        marked("<b>🔎 AVANT-MATCH</b>\nLe coup d’envoi approche.","PREMIUM 2/4"),
        card={"day":day,"league":"Premier League","home":"Arsenal","away":"Chelsea","time":"20h00",
              "home_form":"V • V • N • V • D","away_form":"V • N • V • D • V",
              "home_logo":LOGO_A,"away_logo":LOGO_B}),
      Publication("resultat","test:template:result",
        marked("<b>🏁 RÉSULTAT FINAL</b>\nArsenal s’impose 3-1.","PREMIUM 3/4"),
        card={"day":day,"league":"Premier League","home":"Arsenal","away":"Chelsea","scores":[3,1],
              "source":"TEST","home_logo":LOGO_A,"away_logo":LOGO_B}),
      Publication("composition","test:template:composition",
        marked("<b>📋 COMPOSITIONS OFFICIELLES</b>\nLes titulaires sont confirmés.","PREMIUM 4/4"),
        card={"day":day,"competition":"Ligue des Champions","league":"Ligue des Champions",
              "home":"Arsenal","away":"Chelsea","time":"20h00","source":"TEST",
              "home_players":players_a,"away_players":players_b,
              "home_logo":LOGO_A,"away_logo":LOGO_B}),
    ]

    generic_match={"home":"Arsenal","away":"Chelsea","score":"2-1","minute":67,
                   "player":"TEST JOUEUR","goal":{"player":"Test Joueur"},"home_logo":LOGO_A,"away_logo":LOGO_B}
    items.append(Publication("goal","test:generic:match",
        marked(banner_caption("goal",generic_match),"GÉNÉRIQUE MATCH 1/3"),card=generic_match))

    generic_club={"club":"Arsenal","team":"Arsenal","club_logo":LOGO_A,"team_logo":LOGO_A,
                  "entrant":"Test Entrant","sortant":"Test Sortant","day":day}
    items.append(Publication("changement_composition","test:generic:club",
        marked(banner_caption("changement_composition",generic_club),"GÉNÉRIQUE CLUB 2/3"),card=generic_club))

    generic_general={"headline":"Arsenal domine les tirs cadrés","title":"Arsenal domine les tirs cadrés",
                     "lines":["8 tirs cadrés contre 3","61% de possession"],"confidence":94,"meta":"TEST"}
    items.append(Publication("statistique","test:generic:general",
        marked(banner_caption("statistique_avancee",generic_general),"GÉNÉRIQUE GENERAL 3/3"),
        card=generic_general))

    flash_image="assets/images/article-02bacd1b.webp"
    items.append(Publication("flash","test:flash",
        marked("<b>🚨 TEST INFO FOOT — LE TITRE COMMENCE LE MESSAGE</b>\n\nVoici le résumé court de l’actualité. Le texte va directement à l’essentiel.\n\n<i>(Foot Mercato)</i>","FLASH FOOT"),
        image_path=flash_image))

    quiz_card={"headline":"Quel club a marqué le plus ?","question":"Quel club a marqué le plus ?",
               "options":["Arsenal","Chelsea","Liverpool"],"meta":"QUIZ FOOT"}
    items.append(Publication("quiz","test:quiz",
        marked("<b>🧠 QUIZ FOOT</b>\nÀ vous de jouer 👇","QUIZ"),
        poll=("[TEST] Quel club a marqué le plus ?",["Arsenal","Chelsea","Liverpool"]),
        poll_type="quiz",correct_option_ids=[0],poll_explanation="Réponse de test.",
        poll_description="TEST • Quiz Foot Mr XPRONOS",poll_shuffle=False,poll_allows_revoting=False,
        card=quiz_card))

    vote_card={"headline":"Qui gagne ce match ?","question":"Qui gagne ce match ?",
               "options":["Arsenal","Match nul","Chelsea"],"meta":"VOTE DU JOUR"}
    items.append(Publication("sondage","test:vote",
        marked("<b>🗳️ VOTE DU JOUR</b>\nVotez juste en dessous 👇","SONDAGE"),
        poll=("[TEST] Qui gagne ce match ?",["Arsenal","Match nul","Chelsea"]),
        poll_type="regular",poll_description="TEST • Vote du jour Mr XPRONOS",
        poll_allows_revoting=True,card=vote_card))

    reaction_card={"home":"Arsenal","away":"Chelsea","score":"3-1","question":"Quelle note donnez-vous au match ?",
                   "reaction":"Quelle note donnez-vous au match ?","home_logo":LOGO_A,"away_logo":LOGO_B}
    items.append(Publication("reaction","test:reaction",
        marked("<b>⭐ VOTRE RÉACTION ?</b>\nDonnez votre note juste en dessous 👇","RÉACTION"),
        poll=("[TEST] Quelle note donnez-vous au match ?",["🔥 Excellent","👍 Bon","😐 Moyen"]),
        poll_type="regular",poll_description="TEST • Réaction Mr XPRONOS",
        poll_allows_revoting=True,card=reaction_card))

    sent=[]
    for item in items:
        mid=sender.send(item)
        sent.append((item.category,mid))
    print("ACTU_FOOT_FULL_CHANNEL_TEST",sent)

if __name__=="__main__":
    main()
