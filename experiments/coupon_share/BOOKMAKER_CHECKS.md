# Bookmaker checks — 2026-11-28

Scope: public pages, no login, stake, bet placement, or automatic submission. No live share code was created.

| Site tested with Python HTTPS GET | Result | Public evidence |
|---|---|---|
| https://betwinner.com/ | DNS resolution failed | Betwinner share feature documented on regional pages |
| https://betwinner.ci/fr/betsonyour/line | DNS resolution failed | Public search index describes loading events from a code |
| https://winsport365.com/en/ | DNS resolution failed | Share-code feature not confirmed |
| https://winwin.bet/en | DNS resolution failed | Third-party reports describe save/load, not independently verified |
| https://1win.com/ | DNS resolution failed | Prior prototype only simulated; no live code |

All five requests failed locally with NameResolutionError (temporary failure in name resolution), before an HTTP response. This is an environment limitation, not proof of a bookmaker outage or geographic restriction. Public search index references: https://betwinner.co.mz/en/betsonyour/line (save/share), https://betwinner.ci/fr/betsonyour/line (load); https://predictlix.com/bookmakers/kenya/winwinbet/ (third-party report). Betwinner terms https://betwinner.cm/tr/information/rules/2 restrict automated betting; automated share-only access not established. WinSport365 and WinWin Bet are distinct possible interpretations of Win Sport; confirm intended brand before integration.

No production code changed. A real code creation and reload test remains outstanding. No bypass of access controls or restrictions attempted.
