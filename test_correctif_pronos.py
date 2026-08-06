from pathlib import Path

root = Path(__file__).resolve().parent
main = (root / "assets/js/main.js").read_text(encoding="utf-8")
sw = (root / "service-worker.js").read_text(encoding="utf-8")
html = (root / "pronos.html").read_text(encoding="utf-8")

checks = {
    "Notification protégée": 'if ("Notification" in window && Notification.permission === "granted")' in main,
    "Chargement prioritaire": main.index('if (page === "pronos")') < main.index('await initSupabase();'),
    "Date explicite utilisée": 'function getMatchDate(match)' in main and 'const eventLocalDate = getMatchDate(m);' in main,
    "Cache réseau no-store": 'cache: "no-store"' in main,
    "Conservation cache non vide": 'empty-network-payload' in main,
    "Service worker V12": "v12-pronos-fix" in sw,
    "Clé JSON stable": "stableUrl.search = '';" in sw,
    "Pas de faux data.json vide": "Ne jamais fabriquer un faux data.json vide" in sw,
    "Cache-busting HTML": 'main.js?v=20260806-pronos-fix' in html,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("✅" if ok else "❌"), name)

if failed:
    raise SystemExit("Échec: " + ", ".join(failed))

print("\n✅ Tous les contrôles du correctif Pronostics passent.")
