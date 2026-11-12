"""Editorial popularity ranking for real football fixtures (V2).

No post-match scores, inferred standings, odds, or future data. Numbers are
transparent editorial priorities, NOT measured audiences or betting edges.
"""
from __future__ import annotations

import re
import unicodedata

from .club_registry_world import recognize_club, WORLD_CLUBS

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
    # Wider V3 editorial pool; these are prestige weights, NOT observed audiences.
    "ES:POR.1": 115, "ES:NED.1": 112, "ES:TUR.1": 106,
    "ES:SCO.1": 104, "ES:BEL.1": 105, "ES:ENG.2": 90,
    "ES:BRA.1": 114, "ES:ARG.1": 112, "ES:USA.1": 107,
    "ES:MEX.1": 104, "ES:COL.1": 95, "ES:JPN.1": 100,
    "ES:KOR.1": 95, "ES:KSA.1": 103,
    "ES:EGY.1": 97, "ES:MAR.1": 93, "ES:RSA.1": 94,
    "ES:UEFA.NATIONS": 125,
    "ES:CONMEBOL.LIBERTADORES": 148,
    "ES:CONMEBOL.SUDAMERICANA": 116,
    "ES:CONCACAF.CHAMPIONS": 125,
    "ES:CAF.CHAMPIONS": 130,
    "ES:CAF.CONFEDERATION": 105,
    "ES:AFC.CHAMPIONS": 126,
    "ES:GER.DFB_POKAL": 119,
    "ES:ESP.COPA_DEL_REY": 119,
    "ES:ITA.COPPA_ITALIA": 116,
    "ES:FRA.COUPE_DE_FRANCE": 115,
    "ES:FIFA.WORLDQ.UEFA": 123,
    "ES:FIFA.WORLDQ.CAF": 120,
    "ES:FIFA.WORLDQ.CONMEBOL": 125,
    "ES:CONMEBOL.AMERICA": 158,
    "ES:CAF.NATIONS": 150,
    "ES:CONCACAF.GOLD": 116,
    # International competitions: only used when their source is explicitly enabled.
    "ES:FIFA.WORLD": 185, "ES:UEFA.EURO": 166,
    "ES:CONMEBOL.AMERICA": 157, "ES:CAF.NATIONS": 149,
    "ES:CONCACAF.GOLD": 116,
    # Only for catalogued fallback fixtures; editorial prominence, not audience.
    "ES:FIFA.FRIENDLY": 96, "ES:FIFA.FRIENDLY.W": 84,
    "ES:FIFA.FRIENDLY_U21": 66, "ES:CLUB.FRIENDLY": 71,
    "ES:CONCACAF.NATIONS.LEAGUE": 115,
    "ES:CAF.NATIONS_QUAL": 120,
    "ES:FIFA.WORLDQ.AFC": 122,
    "ES:FIFA.WORLDQ.CONCACAF": 124,
    "ES:FIFA.WORLDQ.OFC": 110,
    "ES:FIFA.WORLD.U20": 87, "ES:FIFA.WORLD.U17": 82,
    "ES:USA.NWSL": 94, "ES:USA.USL.1": 77,
    "ES:USA.USL.L1": 69, "ES:USA.OPEN": 91,
    "ES:MEX.2": 76, "ES:BRA.2": 79,
    "ES:CHI.1": 88, "ES:URU.1": 89,
    "ES:PER.1": 85, "ES:PAR.1": 81, "ES:BOL.1": 78,
    "ES:ECU.1": 85, "ES:VEN.1": 77,
    "ES:ARG.COPA": 100,
    "ES:NGA.1": 82, "ES:GHA.1": 82,
    "ES:AFC.CUP": 113, "ES:CHN.1": 96,
    "ES:IND.1": 82, "ES:THA.1": 85,
    "ES:MYS.1": 81, "ES:IDN.1": 82,
    "ES:SGP.1": 76, "ES:AUS.1": 102,
    "ES:AUS.W.1": 89,
    # Additional documented secondary competitions, still no senior-club
    # bonus for academy/reserve teams.
    "ES:IRL.1": 80, "ES:NOR.1": 88, "ES:SWE.1": 89,
    "ES:DEN.1": 92, "ES:AUT.1": 100,
    "ES:GRE.1": 93, "ES:CYP.1": 83, "ES:RUS.1": 97,
    "ES:ENG.3": 86, "ES:ENG.4": 77, "ES:ENG.5": 71,
    "ES:ENG.W.1": 114, "ES:ESP.2": 89, "ES:ESP.W.1": 105,
    "ES:GER.2": 90, "ES:ITA.2": 88, "ES:FRA.2": 85,
    "ES:FRA.W.1": 96, "ES:NED.2": 82, "ES:NED.3": 73,
    "ES:USA.W.USL.1": 86, "ES:CAN.W.NSL": 83,
    "ES:FIFA.U20.FRIENDLY": 65, "ES:FIFA.WWORLDQ.UEFA": 115,
    "ES:UEFA.W.NATIONS": 107, "ES:NONFIFA": 60,
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
# Editorial country recognition for competitions all over the world. These
# are relative attention labels, never FIFA rankings, results or match odds.
NATIONS.update({
    "uruguay":29,"colombia":30,"chile":27,"peru":24,"ecuador":27,
    "paraguay":25,"bolivia":20,"venezuela":19,"costa rica":23,
    "panama":23,"jamaica":21,"canada":28,"haiti":19,"honduras":19,
    "el salvador":17,"guatemala":18,"trinidad and tobago":19,
    "cuba":16,"dominican republic":17,"curacao":20,
    "united arab emirates":21,"saudi arabia":26,"qatar":24,
    "iran":27,"iraq":24,"jordan":23,"oman":20,"bahrain":18,
    "kuwait":18,"uzbekistan":23,"tajikistan":18,
    "australia":28,"new zealand":23,"china":24,"chinese taipei":16,
    "thailand":22,"vietnam":22,"indonesia":24,"malaysia":21,
    "singapore":18,"india":22,"philippines":20,"lebanon":17,
    "syria":18,"palestine":19,"hong kong":16,
    "sweden":29,"norway":30,"denmark":29,"finland":21,
    "iceland":24,"ireland":23,"northern ireland":20,
    "scotland":27,"wales":25,"switzerland":27,"austria":26,
    "poland":27,"ukraine":27,"czech republic":26,"czechia":26,
    "slovakia":23,"slovenia":24,"croatia":31,"serbia":27,
    "bosnia and herzegovina":22,"montenegro":19,
    "north macedonia":20,"albania":22,"kosovo":23,
    "romania":24,"hungary":24,"greece":26,"turkey":28,
    "georgia":24,"armenia":18,"azerbaijan":18,"cyprus":19,
    "israel":20,"belarus":17,"moldova":17,
    "tunisia":28,"south africa":27,"dr congo":26,
    "democratic republic of congo":26,"guinea":23,"mali":26,
    "burkina faso":25,"benin":20,"uganda":20,"kenya":21,
    "tanzania":21,"zambia":23,"zimbabwe":19,
    "angola":25,"mozambique":21,"cape verde":25,
    "cabo verde":25,"guinea bissau":21,"gabon":22,
    "equatorial guinea":22,"sudan":20,"south sudan":16,
    "mauritania":21,"libya":18,"niger":19,
    "madagascar":20,"comoros":22,"rwanda":20,
    "ethiopia":20,"sierra leone":19,"liberia":18,
})

NATIONAL_CODES = frozenset({"ES:FIFA.WORLD", "ES:UEFA.EURO", "ES:CONMEBOL.AMERICA",
                            "ES:CAF.NATIONS", "ES:CONCACAF.GOLD", "ES:UEFA.NATIONS",
                            "ES:FIFA.WORLDQ.UEFA", "ES:FIFA.WORLDQ.CAF",
                            "ES:FIFA.WORLDQ.CONMEBOL", "ES:FIFA.FRIENDLY",
                            "ES:FIFA.FRIENDLY.W", "ES:CONCACAF.NATIONS.LEAGUE",
                            "ES:CAF.NATIONS_QUAL", "ES:FIFA.WORLDQ.AFC",
                            "ES:FIFA.WORLDQ.CONCACAF", "ES:FIFA.WORLDQ.OFC",
                            "ES:FIFA.FRIENDLY_U21", "ES:FIFA.WORLD.U20",
                            "ES:FIFA.WORLD.U17", "ES:FIFA.U20.FRIENDLY",
                            "ES:FIFA.WWORLDQ.UEFA", "ES:UEFA.W.NATIONS",
                            "ES:NONFIFA"})
WOMENS_CODES = frozenset({"ES:UEFA.WCHAMPIONS","ES:FIFA.FRIENDLY.W",
                          "ES:USA.NWSL","ES:AUS.W.1",
                          "ES:ENG.W.1","ES:ESP.W.1","ES:FRA.W.1",
                          "ES:USA.W.USL.1","ES:CAN.W.NSL",
                          "ES:FIFA.WWORLDQ.UEFA","ES:UEFA.W.NATIONS"})
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
            or re.search(r"\s(?:ii|b)$", n)
            or c in {"ES:FIFA.WORLD.U20","ES:FIFA.WORLD.U17",
                     "ES:FIFA.U20.FRIENDLY","ES:FIFA.FRIENDLY_U21"}):
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
    # A national-team competition is distinct from club competitions even
    # for women's teams. Senior country popularity must not be inherited
    # by U17/U20 teams (guarded above), and women's priority is separate.
    if str(competition).upper() in NATIONAL_CODES:
        value = NATIONS.get(cleaned, 0)
        return cleaned, round(value * .72) if category == "women" else value, category
    if category == "national":
        return cleaned, NATIONS.get(cleaned, 0), category
    # Preserve meaningful literal suffixes when they uniquely identify a
    # different club: "Barcelona SC" (Ecuador) must not become FC Barcelona
    # when the scorer removes a generic "SC" designation.
    literal=normalize(name)
    if literal != cleaned:
        exact=recognize_club(literal, competition,
                             normalize=normalize, women=category=="women")
        if exact is not None:
            return exact[0], exact[1], category
    # First use the exact club identity in its own championship. Promoted and
    # relegated teams may inherit recognition within the same country. In
    # international tournaments, only aliases unique across the worldwide
    # catalogue receive a club weight.
    club = recognize_club(cleaned, competition,
                          normalize=normalize_club, women=category=="women",
                          local_only=True)
    if club is not None:
        return club[0], club[1], category
    # The previously curated worldwide brands retain their precedence in
    # neutral/continental contexts, avoiding deceptive alias collisions
    # between FC Barcelona and Ecuador's Barcelona SC.
    for canonical, (value, aliases) in CLUBS.items():
        if cleaned in {normalize_club(a) for a in aliases}:
            # Female teams have their own editorial tier, not senior full credit.
            if category == "women":
                return canonical, round(value * .72), category
            return canonical, value, category
    club = recognize_club(cleaned, competition,
                          normalize=normalize_club, women=category=="women")
    if club is not None:
        return club[0], club[1], category
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
    # ESPN's aggregate source has no reliable league mapping in each event.
    # Explicitly labelled college matches rank AFTER unspecified ordinary
    # competition fixtures. This is editorial priority, not outcome quality.
    if comp == "ES:ALL" and "ncaa" in normalize(fixture.competition_name):
        total = 28
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
