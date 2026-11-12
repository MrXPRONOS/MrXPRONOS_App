"""Worldwide popular-team editorial registry and source-code coverage audit.

No odds, live final scores, fabricated fixtures, or video renderer changes.
"""
from datetime import datetime, timezone
import pytest

from dcscore.club_registry_world import (
    WORLD_CLUBS, COUNTRY_CUPS, normalize_scope, recognize_club,
    parse_catalog, _indexes,
)
from dcscore.daily_espn import ALLOWED
from dcscore.daily_popularity import (
    normalize_club, club_class, importance_score, NATIONS, WOMENS_CODES,
)
from dcscore.daily_rank import RankedFixture, importance, select_tiered

DATE=datetime(2026,11,14,20,tzinfo=timezone.utc)
SPECIAL_COMPETITIONS=frozenset("""
uefa.champions uefa.europa uefa.europa.conf uefa.wchampions
eng.fa eng.league_cup eng.trophy
fifa.world uefa.euro
uefa.nations conmebol.libertadores conmebol.sudamericana
concacaf.champions caf.champions caf.confederation afc.champions
ger.dfb_pokal esp.copa_del_rey ita.coppa_italia fra.coupe_de_france
fifa.worldq.uefa fifa.worldq.caf fifa.worldq.conmebol
conmebol.america caf.nations concacaf.gold
fifa.friendly fifa.friendly.w fifa.friendly_u21 club.friendly
concacaf.nations.league caf.nations_qual
fifa.worldq.afc fifa.worldq.concacaf fifa.worldq.ofc
fifa.world.u20 fifa.world.u17
usa.open arg.copa afc.cup
fifa.u20.friendly fifa.wworldq.uefa uefa.w.nations
nonfifa all
""".split())


def f(home,away,comp="ES:GER.1",league="Bundesliga"):
    return RankedFixture(id=comp+":"+home+":"+away,
        competition=comp,competition_name=league,kickoff=DATE,
        home_id="h",away_id="a",home_name=home,away_name=away,
        stage="REGULAR_SEASON",source="test",
        source_verified=True)


def test_every_domestic_espn_code_covered_without_exception():
    """The complete configured ESPN catalogue is mapped or explicitly special."""
    all_codes=set(ALLOWED)
    league_codes=set(WORLD_CLUBS)
    uncovered=all_codes-league_codes-SPECIAL_COMPETITIONS
    assert not uncovered, f"ESPN leagues lack known clubs: {sorted(uncovered)}"
    assert not (league_codes-SPECIAL_COMPETITIONS).difference(all_codes)
    assert len(WORLD_CLUBS)>=66
    assert sum(len(tier) for tiers in WORLD_CLUBS.values()
               for tier in tiers)>=650
    for key,tiers in WORLD_CLUBS.items():
        assert len(tiers)==2
        assert sum(len(tier) for tier in tiers)>=5, key


def test_no_duplicate_alias_within_any_one_league_and_no_empty_names():
    local,world,country,women=_indexes(normalize_club)
    assert len(local)==len(WORLD_CLUBS)
    assert len(world)>300
    assert len(country)>300
    assert len(women)>40
    assert all(bool(alias) for entries in local.values() for alias in entries)


@pytest.mark.parametrize("name",[
    "Union Berlin","FC Union Berlin","1. FC Union Berlin",
    "Eintracht Frankfurt","VfB Stuttgart","SC Freiburg",
    "Mainz 05","TSG Hoffenheim","VfL Wolfsburg",
    "Werder Bremen","Borussia Mönchengladbach",
])
def test_german_well_known_clubs_including_berlin(name):
    canonical,points,category=club_class(name,competition="ES:GER.1")
    assert canonical and points>=21 and category=="senior"


def test_german_major_vs_unrecognized_is_promoted_in_ranking():
    known=importance(f("Union Berlin","SC Freiburg"))
    unknown=importance(f("Very Small FC","Unknown Village FC"))
    assert known.importance>=unknown.importance+42
    assert "club_domicile=29" in known.importance_reasons
    assert "club_exterieur=29" in known.importance_reasons


def test_all_league_championships_have_at_least_a_high_priority_team():
    for league,tiers in WORLD_CLUBS.items():
        canonical,weight,aliases=tiers[0][0]
        # A club listed in a domestic women's league is categorized women
        # even when ESPN's team name does not contain a women's suffix.
        score=club_class(canonical,competition="ES:"+league.upper(),
                         competition_name=ALLOWED[league])
        assert score[1]>=21,(league,canonical,score)


@pytest.mark.parametrize("club,code",[
    ("Vissel Kobe","ES:JPN.1"),
    ("FC Tokyo","ES:JPN.1"),
    ("Inter Miami","ES:USA.1"),
    ("River Plate","ES:ARG.1"),
    ("Johor Darul Ta'zim","ES:MYS.1"),
    ("Asante Kotoko","ES:GHA.1"),
    ("Rivers United","ES:NGA.1"),
    ("Mamelodi Sundowns","ES:RSA.1"),
    ("Pyramids FC","ES:EGY.1"),
    ("Atletico Nacional","ES:COL.1"),
    ("Bolivar","ES:BOL.1"),
    ("Al Nassr","ES:KSA.1"),
    ("Buriram United","ES:THA.1"),
    ("Melbourne City","ES:AUS.1"),
    ("Shamrock Rovers","ES:IRL.1"),
    ("Portland Thorns","ES:USA.NWSL"),
])
def test_known_clubs_across_continents(club,code):
    assert club_class(club,competition=code)[1]>=20,(club,code)


def test_promoted_and_relegated_clubs_are_recognized_across_country_divisions():
    assert club_class("Hertha Berlin",competition="ES:GER.1")[1]>=21
    assert club_class("Union Berlin",competition="ES:GER.2")[1]>=21
    assert club_class("Sampdoria",competition="ES:ITA.1")[1]>=21
    assert club_class("Sampdoria",competition="ES:ITA.2")[1]>=21


def test_cups_and_international_football_remain_covered():
    assert club_class("Union Berlin",competition="ES:GER.DFB_POKAL")[1]>=21
    assert club_class("Union Berlin",competition="ES:UEFA.EUROPA")[1]>=21
    assert club_class("Bolivar",competition="ES:CONMEBOL.LIBERTADORES")[1]>=21
    assert club_class("Orlando Pirates",competition="ES:CAF.CHAMPIONS")[1]>=21


def test_unknown_and_ambiguous_names_never_receive_famous_club_score():
    for name in ("United","Rangers FC U21","Union Berlin U21",
                 "Bayern II","Real Madrid Castilla","Union Berlin B"):
        assert club_class(name,competition="ES:GER.1")[1]==0,name
    assert club_class("Nacional",competition="ES:ALL")[1]==0
    assert club_class("Auckland City")[1]==0


def test_senior_and_womens_are_separate_across_same_named_teams():
    senior=club_class("Arsenal",competition="ES:UEFA.CHAMPIONS")
    woman=club_class("Arsenal",competition="ES:ENG.W.1")
    assert senior[1]==40
    assert woman[2]=="women" and 20<=woman[1]<40
    assert club_class("Chelsea Women",competition="ES:UEFA.WCHAMPIONS")[2]=="women"
    assert club_class("Orlando Pride",competition="ES:USA.NWSL")[1]>=21
    assert club_class("Melbourne City",competition="ES:AUS.W.1")[2]=="women"


def test_nations_extended_and_youth_country_does_not_inherit_senior_status():
    assert club_class("Tanzania",competition="ES:CAF.NATIONS")[1]>=20
    assert club_class("Sweden",competition="ES:UEFA.NATIONS")[1]>=20
    assert club_class("Japan",competition="ES:FIFA.WORLD")[1]>=20
    assert club_class("France",competition="ES:FIFA.FRIENDLY.W")[1] < \
           club_class("France",competition="ES:FIFA.WORLD")[1]
    assert club_class("France",competition="ES:FIFA.WORLD.U20")[1]==0


def test_existing_global_derbies_still_highest_and_unknown_clubs_fill():
    big=importance(f("Bayern Munich","Borussia Dortmund"))
    regional=importance(f("Union Berlin","SC Freiburg"))
    other=importance(f("Small Town FC","Village United"))
    assert big.importance>regional.importance>other.importance
    chosen=select_tiered([other,regional,big],limit=3,max_per_league=4)
    assert [x.id for x in chosen]==[big.id,regional.id,other.id]


def test_recognition_does_not_use_results_or_change_model_evidence():
    match=f("Union Berlin","SC Freiburg")
    first=importance(match)
    assert importance(match).importance==first.importance
    assert all("club_" in s or "competition" in s or "deux_grands" in s
               for s in first.importance_reasons)
