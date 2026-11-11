"""Editorial popularity ranking for real football fixtures (V2).

No post-match scores, inferred standings, odds, or future data. Numbers are
transparent editorial priorities, NOT measured audiences or betting edges.
"""
from __future__ import annotations

import re
import unicodedata

# ESPN codes are prefixed ES:; community providers retain their own namespaces.
LEAGUE_WEIGHT = {
    "CL": 168, "ES:UEFA.CHAMPIONS": 168,
    "EL": 145, "ES:UEFA.EUROPA": 145,
    "EC": 128, "ES:UEFA.EUROPA.CONF": 128,
    "ES:UEFA.WCHAMPIONS": 148,
    "PL": 138, "OF:EN.1": 138, "ES:ENG.1": 138,
    "PD": 136, "OF:ES.1": 136, "ES:ESP.1": 136,
    "BL1": 130, "OF:DE.1": 130, "OL:BL1": 130, "ES:GER.1": 130,
    "SA": 130, "OF:IT.1": 130, "ES:ITA.1": 130,
    "FL1": 127, "OF:FR.1": 127, "ES:FRA.1": 127,
    "PPL": 114, "OF:PT.1": 114, "ES:POR.1": 114,
    "DED": 112, "OF:NL.1": 112, "ES:NED.1": 112,
    "BSA": 112, "ES:BRA.1": 112,
    "ES:ENG.FA": 118, "ES:ENG.LEAGUE_CUP": 108,
    "ELC": 87, "OF:EN.2": 87, "ES:ENG.2": 87,
    "OL:BL2": 90, "OL:BL3": 76,
    "ES:ENG.TROPHY": 65,
    # International competitions: only used when their source is explicitly enabled.
    "ES:FIFA.WORLD": 185, "ES:UEFA.EURO": 166,
    "ES:CONMEBOL.AMERICA": 157, "ES:CAF.NATIONS": 149,
    "ES:CONCACAF.GOLD": 116,
}
STAGE_WEIGHT = {
    "FINAL": 225, "SEMI_FINALS": 105, "QUARTER_FINALS": 62,
    "LAST_16": 35, "LAST_32": 18, "KNOCKOUT": 16, "PLAYOFFS": 38,
    "CHAMPIONSHIP": 22, "CHAMPIONSHIP_ROUND": 22,
}
STAGE_ALIASES = {
    "FINAL": "FINAL", "FINALE": "FINAL",
    "SEMI_FINAL": "SEMI_FINALS", "SEMI_FINALS": "SEMI_FINALS",
    "SEMIFINAL": "SEMI_FINALS", "SEMIFINALS": "SEMI_FINALS",
    "QUARTER_FINAL": "QUARTER_FINALS", "QUARTER_FINALS": "QUARTER_FINALS",
    "QUARTERFINAL": "QUARTER_FINALS", "QUARTERFINALS": "QUARTER_FINALS",
    "ROUND_OF_16": "LAST_16", "ROUND_16": "LAST_16", "LAST_16": "LAST_16",
    "EIGHTH_FINALS": "LAST_16", "ROUND_OF_32": "LAST_32",
    "PLAYOFF": "PLAYOFFS", "PLAYOFFS": "PLAYOFFS",
    "KNOCKOUT_ROUND": "KNOCKOUT",
    "GROUP_STAGE": "GROUP_STAGE", "LEAGUE_PHASE": "LEAGUE_PHASE",
    "REGULAR_SEASON": "REGULAR_SEASON", "CHAMPIONSHIP": "CHAMPIONSHIP",
    "CHAMPIONSHIP_ROUND": "CHAMPIONSHIP_ROUND",
}

# Exact alias lookup avoids accidental inheritance of a famous senior team
# by a U21, academy, reserve or otherwise different squad.
CLUBS = {
    "real madrid": (43, ("real madrid", "real madrid cf")),
    "barcelona": (43, ("barcelona", "fc barcelona")),
    "bayern": (42, ("bayern munich", "bayern munchen", "fc bayern munchen", "fc bayern munich")),
    "manchester city": (41, ("manchester city", "man city")),
    "liverpool": (41, ("liverpool",)),
    "arsenal": (40, ("arsenal",)),
    "paris saint germain": (41, ("paris saint germain", "paris st germain", "psg", "paris sg")),
    "manchester united": (39, ("manchester united", "man united", "man utd")),
    "chelsea": (39, ("chelsea",)),
    "internazionale": (39, ("internazionale", "inter milan", "inter")),
    "juventus": (38, ("juventus",)),
    "atletico madrid": (39, ("atletico madrid", "atletico de madrid")),
    "borussia dortmund": (38, ("borussia dortmund", "dortmund")),
    "milan": (37, ("milan", "ac milan")),
    "napoli": (34, ("napoli",)),
    "tottenham": (33, ("tottenham", "tottenham hotspur", "spurs")),
    "newcastle": (32, ("newcastle", "newcastle united")),
    "bayer leverkusen": (34, ("bayer leverkusen", "leverkusen")),
    "rb leipzig": (30, ("rb leipzig", "rasenballsport leipzig")),
    "benfica": (35, ("benfica", "sl benfica")),
    "porto": (33, ("porto", "fc porto")),
    "sporting": (32, ("sporting cp", "sporting lisbon", "sporting clube de portugal")),
    "ajax": (32, ("ajax", "ajax amsterdam")),
    "psv": (30, ("psv", "psv eindhoven")),
    "feyenoord": (30, ("feyenoord", "feyenoord rotterdam")),
    "marseille": (31, ("olympique marseille", "olympique de marseille", "marseille")),
    "lyon": (30, ("olympique lyonnais", "lyon")),
    "monaco": (30, ("monaco", "as monaco")),
    "lille": (26, ("lille", "lille osc")),
    "nice": (24, ("nice", "ogc nice")),
    "roma": (30, ("roma", "as roma")),
    "lazio": (28, ("lazio", "ss lazio")),
    "atalanta": (30, ("atalanta",)),
    "fiorentina": (25, ("fiorentina",)),
    "sevilla": (26, ("sevilla", "sevilla fc")),
    "real betis": (27, ("real betis", "betis")),
    "athletic club": (27, ("athletic club", "athletic bilbao")),
    "real sociedad": (26, ("real sociedad",)),
    "valencia": (24, ("valencia",)),
    "villarreal": (26, ("villarreal",)),
    "celtic": (30, ("celtic",)),
    "rangers": (29, ("rangers", "glasgow rangers")),
    "galatasaray": (30, ("galatasaray",)),
    "fenerbahce": (29, ("fenerbahce",)),
    "besiktas": (25, ("besiktas",)),
    "braga": (24, ("braga", "sc braga")),
    "boca juniors": (35, ("boca juniors",)),
    "river plate": (35, ("river plate",)),
    "flamengo": (35, ("flamengo",)),
    "palmeiras": (35, ("palmeiras",)),
    "santos": (27, ("santos",)),
    "sao paulo": (31, ("sao paulo",)),
    "al ahly": (33, ("al ahly", "al ahly cairo", "alahly")),
    "zamalek": (29, ("zamalek", "zamalek sc")),
    "wydad": (30, ("wydad", "wydad casablanca", "wydad ac")),
    "raja": (29, ("raja", "raja casablanca", "raja ca")),
    "esperance tunis": (29, ("esperance tunis", "esperance sportive de tunis", "esperance")),
    "mamelodi sundowns": (30, ("mamelodi sundowns",)),
    "tp mazembe": (28, ("tp mazembe", "mazembe")),
    "asec mimosas": (26, ("asec mimosas",)),
}

# FIFA team popularity is a separate table, never inferred from club names.
NATIONS = {
    "argentina": 43, "france": 42, "brazil": 42, "brasil": 42,
    "spain": 42, "espana": 42, "england": 40, "germany": 40,
    "portugal": 39, "italy": 38, "netherlands": 36, "belgium": 33,
    "morocco": 35, "senegal": 32, "nigeria": 32, "cote d ivoire": 32,
    "cameroon": 31, "algeria": 30, "ghana": 29, "egypt": 29,
    "japan": 29, "south korea": 29, "united states": 29,
    "usa": 29, "mexico": 29, "togo": 19,
}
NATIONAL_CODES = frozenset({"ES:FIFA.WORLD", "ES:UEFA.EURO", "ES:CONMEBOL.AMERICA",
                            "ES:CAF.NATIONS", "ES:CONCACAF.GOLD"})
WOMENS_CODES = frozenset({"ES:UEFA.WCHAMPIONS"})
DERBIES = (
    frozenset(("real madrid", "barcelona")),
    frozenset(("real madrid", "atletico madrid")),
    frozenset(("barcelona", "atletico madrid")),
    frozenset(("manchester city", "manchester united")),
    frozenset(("liverpool", "manchester united")),
    frozenset(("arsenal", "tottenham")),
    frozenset(("arsenal", "chelsea")),
    frozenset(("milan", "internazionale")),
    frozenset(("juventus", "internazionale")),
    frozenset(("bayern", "borussia dortmund")),
    frozenset(("paris saint germain", "marseille")),
    frozenset(("boca juniors", "river plate")),
    frozenset(("celtic", "rangers")),
    frozenset(("fenerbahce", "galatasaray")),
    frozenset(("wydad", "raja")),
    frozenset(("al ahly", "zamalek")),
)
TEAM_WEIGHT = {name: score for name, (score, _) in CLUBS.items()}


def normalize(text: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", str(text).casefold())
                if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def normalize_club(name: str) -> str:
    value = normalize(name)
    # These are club-designation tokens only, not substrings.
    value = re.sub(r"^(?:fc|cf|ac|as|sc|afc|rc|ssc)\s+", "", value)
    value = re.sub(r"\s+(?:fc|cf|sc|afc|football club)$", "", value)
    return value


def squad_category(name: str, competition: str = "", competition_name: str = "") -> str:
    n = normalize(name)
    c = str(competition).upper()
    league_name = normalize(competition_name)
    # Youth/reserves supersede a women's category: the senior brand is not inherited.
    if (re.search(r"\b(?:u(?:17|18|19|20|21|23)|under (?:17|18|19|20|21|23)|"
                  r"academy|youth|reserves?|development|primavera|castilla)\b", n)
            or re.search(r"\s(?:ii|b)$", n)):
        return "youth_reserve"
    if (re.search(r"\b(?:women|womens|wfc|ladies|feminin|feminine|femenino|"
                  r"femenina|frauen|damen)\b", n)
            or c in WOMENS_CODES or "women" in league_name
            or "feminin" in league_name or "femenin" in league_name):
        return "women"
    if c in NATIONAL_CODES:
        return "national"
    return "senior"


def club_class(name: str, *, competition: str = "", competition_name: str = "") -> tuple[str, int, str]:
    category = squad_category(name, competition, competition_name)
    if category == "youth_reserve":
        return "", 0, category
    cleaned = normalize_club(name)
    if category == "women":
        cleaned = re.sub(r"\s+(?:women|womens|wfc|ladies|feminine|feminin|"
                         r"femenino|femenina|frauen|damen)$", "", cleaned)
        cleaned = normalize_club(cleaned)
    if category == "national":
        return cleaned, NATIONS.get(cleaned, 0), category
    for canonical, (value, aliases) in CLUBS.items():
        if cleaned in {normalize_club(a) for a in aliases}:
            # Female teams have their own editorial tier, not senior full credit.
            if category == "women":
                return canonical, round(value * .72), category
            return canonical, value, category
    return "", 0, category


def _team_class(name: str) -> tuple[str, int]:
    club, weight, _ = club_class(name)
    return club, weight


def stage_class(value: str) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_")
    return STAGE_ALIASES.get(code, code)


def importance_score(fixture) -> tuple[int, tuple[str, ...]]:
    comp = fixture.competition.upper()
    stage = stage_class(fixture.stage)
    total = LEAGUE_WEIGHT.get(comp, 60)
    reasons = [f"competition={total}"]
    hkey, hweight, htype = club_class(fixture.home_name, competition=comp,
                                      competition_name=fixture.competition_name)
    akey, aweight, atype = club_class(fixture.away_name, competition=comp,
                                      competition_name=fixture.competition_name)
    if hweight:
        total += hweight
        reasons.append(f"club_domicile={hweight}")
    if aweight:
        total += aweight
        reasons.append(f"club_exterieur={aweight}")
    if htype == "youth_reserve" or atype == "youth_reserve":
        # A U21 or reserve side may not claim its senior club's popularity.
        # It also gets a strong editorial downranking (not a betting judgement).
        total -= 60
        reasons.append("equipe_jeunes_reserve=-60")
    else:
        cutoff = 20 if htype == atype == "women" else 29
        if hweight >= cutoff and aweight >= cutoff:
            total += 28
            reasons.append("deux_grands_clubs=28")
        if hkey and akey and frozenset((hkey, akey)) in DERBIES and htype == atype:
            total += 75
            reasons.append("derby_reconnu=75")
    if stage in STAGE_WEIGHT:
        value = STAGE_WEIGHT[stage]
        total += value
        reasons.append(f"tour_{stage.lower()}={value}")
    return total, tuple(reasons)
