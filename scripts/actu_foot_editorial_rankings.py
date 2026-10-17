"""Classements éditoriaux Actu Foot.

- Clubs: hiérarchie de notoriété/prestige adaptée au public Mr XPRONOS, élargie
  à 100 clubs. La présence et la forme récente ont été recoupées avec les
  classements mondiaux FootballDatabase du 11 octobre 2026.
- Sélections: Top 100 FIFA masculin officiel du 7 octobre 2026.
- Compétitions: hiérarchie éditoriale de 100 compétitions/championnats,
  construite pour la sélection média; les ligues nationales s'appuient sur
  l'ordre de force IFFHS récent, tandis que les grandes compétitions
  internationales sont volontairement surpondérées pour leur intérêt média.

Ces listes servent à classer les affiches, pas à prédire le résultat d'un match.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any

CLUB_RANKING = (
    (1, "Real Madrid"),
    (2, "Barcelona"),
    (3, "Manchester United"),
    (4, "Liverpool"),
    (5, "Bayern Munich"),
    (6, "Manchester City"),
    (7, "Arsenal"),
    (8, "Paris Saint-Germain"),
    (9, "AC Milan"),
    (10, "Juventus"),
    (11, "Inter Milan"),
    (12, "Chelsea"),
    (13, "Atletico Madrid"),
    (14, "Borussia Dortmund"),
    (15, "Tottenham Hotspur"),
    (16, "Napoli"),
    (17, "Benfica"),
    (18, "FC Porto"),
    (19, "Ajax"),
    (20, "Flamengo"),
    (21, "Palmeiras"),
    (22, "Boca Juniors"),
    (23, "River Plate"),
    (24, "AS Roma"),
    (25, "Marseille"),
    (26, "Sporting CP"),
    (27, "Newcastle United"),
    (28, "Bayer Leverkusen"),
    (29, "PSV Eindhoven"),
    (30, "Feyenoord"),
    (31, "Al Ahly"),
    (32, "Galatasaray"),
    (33, "Fenerbahce"),
    (34, "Celtic"),
    (35, "Rangers"),
    (36, "Lyon"),
    (37, "Monaco"),
    (38, "Sevilla"),
    (39, "Athletic Bilbao"),
    (40, "Real Sociedad"),
    (41, "Villarreal"),
    (42, "Atalanta"),
    (43, "Lazio"),
    (44, "RB Leipzig"),
    (45, "Aston Villa"),
    (46, "Club Brugge"),
    (47, "Olympiacos"),
    (48, "Red Star Belgrade"),
    (49, "Shakhtar Donetsk"),
    (50, "Wydad Casablanca"),
    (51, "Raja Casablanca"),
    (52, "Esperance Tunis"),
    (53, "Mamelodi Sundowns"),
    (54, "TP Mazembe"),
    (55, "Zamalek"),
    (56, "Pyramids FC"),
    (57, "Al Hilal"),
    (58, "Al Nassr"),
    (59, "Al Ittihad"),
    (60, "Al Ahli Saudi"),
    (61, "Inter Miami"),
    (62, "Club America"),
    (63, "Cruz Azul"),
    (64, "Monterrey"),
    (65, "Tigres UANL"),
    (66, "Sao Paulo"),
    (67, "Corinthians"),
    (68, "Fluminense"),
    (69, "Gremio"),
    (70, "Internacional"),
    (71, "Santos"),
    (72, "Atletico Mineiro"),
    (73, "Athletico Paranaense"),
    (74, "Botafogo"),
    (75, "Cruzeiro"),
    (76, "Racing Club"),
    (77, "Independiente"),
    (78, "San Lorenzo"),
    (79, "Velez Sarsfield"),
    (80, "Rosario Central"),
    (81, "Estudiantes"),
    (82, "LDU Quito"),
    (83, "Independiente del Valle"),
    (84, "Atletico Nacional"),
    (85, "Millonarios"),
    (86, "Colo-Colo"),
    (87, "Universidad de Chile"),
    (88, "Penarol"),
    (89, "Nacional"),
    (90, "Braga"),
    (91, "Besiktas"),
    (92, "Salzburg"),
    (93, "Dinamo Zagreb"),
    (94, "Slavia Prague"),
    (95, "Sparta Prague"),
    (96, "Anderlecht"),
    (97, "Genk"),
    (98, "Union Saint-Gilloise"),
    (99, "PAOK"),
    (100, "AEK Athens"),
)

NATIONAL_TEAM_RANKING = (
    (1, "Spain"),
    (2, "Argentina"),
    (3, "France"),
    (4, "England"),
    (5, "Portugal"),
    (6, "Brazil"),
    (7, "Morocco"),
    (8, "Belgium"),
    (9, "Netherlands"),
    (10, "Mexico"),
    (11, "Colombia"),
    (12, "Switzerland"),
    (13, "Germany"),
    (14, "Croatia"),
    (15, "Italy"),
    (16, "United States"),
    (17, "Japan"),
    (18, "Senegal"),
    (19, "Norway"),
    (20, "Uruguay"),
    (21, "Denmark"),
    (22, "Austria"),
    (23, "Iran"),
    (24, "Ecuador"),
    (25, "Egypt"),
    (26, "Australia"),
    (27, "Canada"),
    (28, "Algeria"),
    (29, "Ivory Coast"),
    (30, "Nigeria"),
    (31, "Turkey"),
    (32, "South Korea"),
    (33, "Paraguay"),
    (34, "Sweden"),
    (35, "Russia"),
    (36, "Ukraine"),
    (37, "Poland"),
    (38, "Hungary"),
    (39, "Wales"),
    (40, "DR Congo"),
    (41, "Greece"),
    (42, "Cameroon"),
    (43, "Scotland"),
    (44, "Serbia"),
    (45, "Slovakia"),
    (46, "Panama"),
    (47, "Mali"),
    (48, "South Africa"),
    (49, "Venezuela"),
    (50, "Chile"),
    (51, "Czechia"),
    (52, "Slovenia"),
    (53, "Peru"),
    (54, "Costa Rica"),
    (55, "Saudi Arabia"),
    (56, "Republic of Ireland"),
    (57, "Bosnia and Herzegovina"),
    (58, "Romania"),
    (59, "Uzbekistan"),
    (60, "Qatar"),
    (61, "Tunisia"),
    (62, "Burkina Faso"),
    (63, "Iraq"),
    (64, "Northern Ireland"),
    (65, "United Arab Emirates"),
    (66, "Albania"),
    (67, "Honduras"),
    (68, "Cape Verde"),
    (69, "Jamaica"),
    (70, "Ghana"),
    (71, "North Macedonia"),
    (72, "Jordan"),
    (73, "Iceland"),
    (74, "Georgia"),
    (75, "Finland"),
    (76, "Kosovo"),
    (77, "Israel"),
    (78, "Bolivia"),
    (79, "Montenegro"),
    (80, "Curacao"),
    (81, "Oman"),
    (82, "Guinea"),
    (83, "Angola"),
    (84, "Haiti"),
    (85, "Gabon"),
    (86, "Syria"),
    (87, "Uganda"),
    (88, "New Zealand"),
    (89, "Benin"),
    (90, "Bulgaria"),
    (91, "Zambia"),
    (92, "Palestine"),
    (93, "Thailand"),
    (94, "Belarus"),
    (95, "Guatemala"),
    (96, "China PR"),
    (97, "Bahrain"),
    (98, "Mozambique"),
    (99, "Vietnam"),
    (100, "Tajikistan"),
)

COMPETITION_RANKING = (
    (1, "FIFA World Cup"),
    (2, "UEFA Champions League"),
    (3, "UEFA European Championship"),
    (4, "Copa America"),
    (5, "Copa Libertadores"),
    (6, "Africa Cup of Nations"),
    (7, "Premier League"),
    (8, "La Liga"),
    (9, "Serie A"),
    (10, "Bundesliga"),
    (11, "Ligue 1"),
    (12, "UEFA Europa League"),
    (13, "FIFA Club World Cup"),
    (14, "CAF Champions League"),
    (15, "Brasileirao Serie A"),
    (16, "Liga Profesional Argentina"),
    (17, "Primeira Liga"),
    (18, "Eredivisie"),
    (19, "Liga MX"),
    (20, "Saudi Pro League"),
    (21, "UEFA Conference League"),
    (22, "Copa Sudamericana"),
    (23, "CAF Confederation Cup"),
    (24, "AFC Champions League Elite"),
    (25, "CONCACAF Champions Cup"),
    (26, "FA Cup"),
    (27, "Copa del Rey"),
    (28, "Coppa Italia"),
    (29, "DFB-Pokal"),
    (30, "Coupe de France"),
    (31, "UEFA Nations League"),
    (32, "CONCACAF Gold Cup"),
    (33, "AFC Asian Cup"),
    (34, "Club World Cup qualifying/playoff"),
    (35, "Egyptian Premier League"),
    (36, "Botola Pro"),
    (37, "Algerian Ligue 1"),
    (38, "South African Premiership"),
    (39, "Tunisian Ligue 1"),
    (40, "Belgian Pro League"),
    (41, "Turkish Super Lig"),
    (42, "Scottish Premiership"),
    (43, "Greek Super League"),
    (44, "Czech First League"),
    (45, "Austrian Bundesliga"),
    (46, "Swiss Super League"),
    (47, "Danish Superliga"),
    (48, "Norwegian Eliteserien"),
    (49, "Swedish Allsvenskan"),
    (50, "Croatian HNL"),
    (51, "Serbian SuperLiga"),
    (52, "Ukrainian Premier League"),
    (53, "Russian Premier League"),
    (54, "Polish Ekstraklasa"),
    (55, "Romanian Liga I"),
    (56, "Hungarian NB I"),
    (57, "MLS"),
    (58, "Liga 1 Colombia"),
    (59, "Ecuadorian Serie A"),
    (60, "Uruguayan Primera Division"),
    (61, "Paraguayan Primera Division"),
    (62, "Chilean Primera Division"),
    (63, "Peruvian Liga 1"),
    (64, "Liga Profesional Bolivia"),
    (65, "Venezuelan Primera Division"),
    (66, "J1 League"),
    (67, "K League 1"),
    (68, "Chinese Super League"),
    (69, "A-League Men"),
    (70, "Qatar Stars League"),
    (71, "UAE Pro League"),
    (72, "Iran Persian Gulf Pro League"),
    (73, "Iraqi Stars League"),
    (74, "Jordan Pro League"),
    (75, "Indian Super League"),
    (76, "Thai League 1"),
    (77, "Uzbekistan Super League"),
    (78, "CAF Super Cup"),
    (79, "UEFA Super Cup"),
    (80, "Recopa Sudamericana"),
    (81, "Community Shield"),
    (82, "EFL Cup"),
    (83, "Supercopa de Espana"),
    (84, "Supercoppa Italiana"),
    (85, "Trophee des Champions"),
    (86, "DFL-Supercup"),
    (87, "KNVB Cup"),
    (88, "Taca de Portugal"),
    (89, "Copa do Brasil"),
    (90, "Copa Argentina"),
    (91, "Coupe du Trone"),
    (92, "Egypt Cup"),
    (93, "Nedbank Cup"),
    (94, "Tunisian Cup"),
    (95, "Algerian Cup"),
    (96, "Saudi King's Cup"),
    (97, "Emperor's Cup"),
    (98, "Korean FA Cup"),
    (99, "Leagues Cup"),
    (100, "FIFA World Cup Qualifiers"),
)

ALIASES = {
    "barcelone":"barcelona","fc barcelona":"barcelona",
    "man city":"manchester city","man united":"manchester united","man utd":"manchester united",
    "psg":"paris saint germain","paris saint-germain":"paris saint germain",
    "fc bayern":"bayern munich","bayern munchen":"bayern munich","bayern münchen":"bayern munich",
    "internazionale":"inter milan","internazionale milano":"inter milan",
    "milan":"ac milan","atletico de madrid":"atletico madrid","atlético madrid":"atletico madrid",
    "dortmund":"borussia dortmund","spurs":"tottenham hotspur",
    "ssc napoli":"napoli","sl benfica":"benfica","porto":"fc porto",
    "sporting":"sporting cp","sporting lisbon":"sporting cp",
    "afc ajax":"ajax","ajax amsterdam":"ajax","psv":"psv eindhoven",
    "olympique de marseille":"marseille","om":"marseille",
    "olympique lyonnais":"lyon","as monaco":"monaco",
    "al ahly cairo":"al ahly","alahly":"al ahly",
    "wydad":"wydad casablanca","wydad ac":"wydad casablanca",
    "raja":"raja casablanca","raja ca":"raja casablanca",
    "esperance de tunis":"esperance tunis","esperance sportive de tunis":"esperance tunis",
    "sundowns":"mamelodi sundowns","mazembe":"tp mazembe",
    "al hilal riyadh":"al hilal","al nassr riyadh":"al nassr",
    "al ittihad jeddah":"al ittihad","al ahli":"al ahli saudi",
    "sao paulo fc":"sao paulo","são paulo":"sao paulo",
    "gremio":"gremio","grêmio":"gremio",
    "athletico pr":"athletico paranaense","atletico pr":"athletico paranaense",
    "nacional montevideo":"nacional","penarol":"penarol","peñarol":"penarol",
    "red star":"red star belgrade","fk red star belgrade":"red star belgrade",
    "olympiacos":"olympiacos","olympiakos":"olympiacos",
    "rb salzburg":"salzburg","red bull salzburg":"salzburg",
    "aek":"aek athens",
    "usa":"united states","united states of america":"united states",
    "ir iran":"iran","cote d ivoire":"ivory coast","côte d'ivoire":"ivory coast",
    "turkiye":"turkey","türkiye":"turkey","korea republic":"south korea",
    "congo dr":"dr congo","democratic republic of congo":"dr congo",
    "cabo verde":"cape verde","curacao":"curacao","curaçao":"curacao",
    "republic of ireland":"republic of ireland","china":"china pr",
}

COMPETITION_ALIASES = {
    "champions league":"uefa champions league","ligue des champions":"uefa champions league",
    "uefa champions league":"uefa champions league",
    "ucl":"uefa champions league","europa league":"uefa europa league",
    "conference league":"uefa conference league","europa conference league":"uefa conference league",
    "world cup":"fifa world cup","coupe du monde":"fifa world cup",
    "euro":"uefa european championship","uefa euro":"uefa european championship",
    "afcon":"africa cup of nations","can":"africa cup of nations","coupe d afrique":"africa cup of nations",
    "libertadores":"copa libertadores","sudamericana":"copa sudamericana",
    "premier league":"premier league","english premier league":"premier league",
    "england premier league":"premier league",
    "laliga":"la liga","la liga":"la liga","serie a":"serie a",
    "bundesliga":"bundesliga","ligue 1":"ligue 1",
    "brasileirao":"brasileirao serie a","brazilian serie a":"brasileirao serie a",
    "liga profesional":"liga profesional argentina","argentinian primera division":"liga profesional argentina",
    "primeira liga":"primeira liga","eredivisie":"eredivisie","liga mx":"liga mx",
    "saudi pro league":"saudi pro league","caf champions league":"caf champions league",
    "caf confederation cup":"caf confederation cup","afc champions league":"afc champions league elite",
    "concacaf champions cup":"concacaf champions cup","major league soccer":"mls","mls":"mls",
    "super lig":"turkish super lig","süper lig":"turkish super lig",
}

def normalize(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii","ignore").decode().casefold()
    value = re.sub(r"\b(fc|cf|sc|afc|club|football|the)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def _index(rows):
    return {normalize(name): rank for rank, name in rows}

CLUB_INDEX = _index(CLUB_RANKING)
NATIONAL_INDEX = _index(NATIONAL_TEAM_RANKING)
COMPETITION_INDEX = _index(COMPETITION_RANKING)

for alias, canonical in list(ALIASES.items()):
    target = normalize(canonical)
    if target in CLUB_INDEX:
        CLUB_INDEX[normalize(alias)] = CLUB_INDEX[target]
    if target in NATIONAL_INDEX:
        NATIONAL_INDEX[normalize(alias)] = NATIONAL_INDEX[target]

for alias, canonical in COMPETITION_ALIASES.items():
    target = normalize(canonical)
    if target in COMPETITION_INDEX:
        COMPETITION_INDEX[normalize(alias)] = COMPETITION_INDEX[target]

def club_rank(name: Any) -> int | None:
    return CLUB_INDEX.get(normalize(name))

def national_rank(name: Any) -> int | None:
    return NATIONAL_INDEX.get(normalize(name))

def competition_rank(name: Any) -> int | None:
    normalized = normalize(name)
    if normalized in COMPETITION_INDEX:
        return COMPETITION_INDEX[normalized]

    # Ne jamais donner le prestige d'une compétition connue à un nom étranger
    # qui ne fait que contenir les mêmes mots:
    # "Libyan Premier League" != Premier League anglaise,
    # "Chinese Football Champions League" != UEFA Champions League.
    # On autorise seulement un suffixe de saison/phase APRÈS un nom reconnu.
    best = None
    for key, rank in COMPETITION_INDEX.items():
        if key and normalized.startswith(key + " "):
            best = rank if best is None else min(best, rank)
    return best

def team_rank(name: Any) -> tuple[str, int] | None:
    c = club_rank(name)
    n = national_rank(name)
    if c is not None and (n is None or c <= n):
        return ("club", c)
    if n is not None:
        return ("national", n)
    return None

def rank_weight(rank: int | None, *, ceiling: int = 300) -> int:
    if rank is None:
        return 0
    rank = max(1, min(100, int(rank)))
    return max(1, ceiling - (rank - 1) * 2)
