"""World editorial club recognition. Not standings, odds or betting quality.

Every domestic ESPN competition is covered (men, women, lower divisions).
A club may change division: exact aliases are also indexed by country.
Cups and cross-border competitions use only unambiguous club identities.
"""
from __future__ import annotations

RAW_CATALOG = "eng.1:aston villa|west ham united|everton|brighton=brighton and hove albion|nottingham forest|crystal palace|fulham|brentford;wolverhampton wanderers=wolves|bournemouth|leeds united|sunderland|burnley|southampton\neng.2:west bromwich albion=west brom|norwich city|coventry city|middlesbrough|watford|stoke city|swansea city;derby county|hull city|preston north end|bristol city|millwall|queens park rangers=qpr|portsmouth\neng.3:bolton wanderers|reading|huddersfield town|barnsley|blackpool|peterborough united;wycombe wanderers|wigan athletic|lincoln city|rotherham united|stockport county|exeter city\neng.4:notts county|bradford city|salford city|chesterfield|gillingham|swindon town;milton keynes dons=mk dons|colchester united|grimsby town|crewe alexandra|walsall\neng.5:rochdale|oldham athletic|hartlepool united|southend united|yeovil town|forest green rovers;york city|solihull moors|boreham wood|halifax town|eastleigh\nesp.1:girona|celta vigo=celta de vigo|osasuna|getafe|rayo vallecano|espanyol|mallorca|real oviedo;alaves=deportivo alaves|levante|elche|las palmas|leganes|granada|cadiz\nesp.2:deportivo la coruna=deportivo|real zaragoza|sporting gijon=real sporting de gijon|racing santander|malaga|almeria;burgos cf=burgos|mirandes|eibar|huesca|cordoba cf|albacete balompie=albacete\nger.1:eintracht frankfurt|vfb stuttgart=stuttgart|1 fc union berlin=union berlin,fc union berlin,1. fc union berlin|sc freiburg=freiburg,sport club freiburg|werder bremen|borussia monchengladbach=borussia moenchengladbach,gladbach|tsg hoffenheim=hoffenheim|vfl wolfsburg=wolfsburg|1 fsv mainz 05=mainz 05,mainz|fc augsburg=augsburg;1 fc koln=fc koln,koln,cologne|hamburger sv=hsv|schalke 04=fc schalke 04,schalke|1 fc heidenheim=heidenheim|vfl bochum=bochum|holstein kiel|st pauli=fc st pauli|sv elversberg|sc paderborn 07=paderborn\nger.2:hertha berlin=hertha bsc|hamburger sv=hsv|schalke 04|1 fc kaiserslautern=kaiserslautern|fortuna dusseldorf=fortuna duesseldorf|hannover 96;karlsruher sc=karlsruhe|1 fc nurnberg=fc nurnberg,nurnberg|darmstadt 98|greuther furth|magdeburg|eintracht braunschweig\nita.1:bologna|torino|genoa|udinese|parma|como 1907=como|cagliari|sampdoria|sassuolo;lecce|hellas verona=verona|empoli|monza|pisa|cremonese|venezia\nita.2:palermo|sampdoria|bari=ssc bari|spezia|venezia|modena|cesena;catanzaro|frosinone|reggiana|pescara|mantova|sudtirol=fc sudtirol\nfra.1:lens=rc lens|rennes=stade rennais|strasbourg=rc strasbourg|nantes=fc nantes|toulouse|brest=stade brestois|montpellier|reims=stade de reims;auxerre=aj auxerre|metz=fc metz|angers|le havre|lorient|saint etienne=as saint etienne|paris fc\nfra.2:saint etienne|caen|bastia=sc bastia|guingamp|red star fc=red star|grenoble foot 38=grenoble|sochaux;amiens|troyes=estac|dunkerque|pau fc|rodez|annecy|laval\npor.1:vitoria guimaraes=vitoria sc|famalicao|estoril|boavista|gil vicente|rio ave|moreirense;casa pia|arouca|santa clara|nacional madeira=cd nacional|farense\nned.1:az alkmaar=az|fc twente=twente|fc utrecht=utrecht|sc heerenveen=heerenveen|fc groningen=groningen|nec nijmegen=nec|sparta rotterdam;go ahead eagles|pec zwolle|nac breda=nac|fortuna sittard|heracles almelo|rkc waalwijk\nned.2:ado den haag=den haag|fc eindhoven|fc emmen=emmen|de graafschap|vitesse arnhem=vitesse|roda jc=roda kerkrade;jong ajax|jong psv|jong az|fc den bosch|vvv venlo|helmond sport\nned.3:afc amsterdam|ijsselmeervogels|spakenburg|katwijk|quick boys|hardenberg;rijnsburgse boys|noordwijk|excelsior maassluis\ntur.1:trabzonspor|istanbul basaksehir=basaksehir|samsunspor|goztepe|kasimpasa|adana demirspor|antalyaspor;konyaspor|gaziantep fk|alanyaspor|rizespor=caykur rizespor|eyupspor|kayserispor\nsco.1:aberdeen|hearts=heart of midlothian|hibernian|dundee united|motherwell|st mirren;kilmarnock|dundee fc|st johnstone|livingston|ross county|falkirk\nbel.1:club brugge=club brugge kv|anderlecht=rsc anderlecht|union saint gilloise=union st gilloise,royale union saint gilloise|genk=krc genk|royal antwerp=antwerp|gent=kaa gent;standard liege=standard de liege|mechelen=kv mechelen|cercle brugge|charleroi|westerlo|oh leuven\nbra.1:fluminense|botafogo|corinthians|gremio|internacional porto alegre=internacional|cruzeiro|atletico mineiro=atletico mg|vasco da gama;bahia=ec bahia|fortaleza|athletico paranaense=atletico paranaense|bragantino=red bull bragantino|ceara|vitoria salvador=ec vitoria\nbra.2:sport recife|america mineiro=america mg|coritiba|goias|chapecoense|avai|atletico goianiense=atletico go;remo|paysandu|ponte preta|guarani campinas=guarani|criciuma|operario ferroviario\narg.1:racing club avellaneda=racing club,racing avellaneda|independiente avellaneda=independiente|san lorenzo|estudiantes la plata=estudiantes de la plata|velez sarsfield=velez|rosario central;newells old boys=newells|talleres cordoba=talleres|lanus=club atletico lanus|huracan|defensa y justicia|argentinos juniors\nusa.1:inter miami=inter miami cf|la galaxy=los angeles galaxy|lafc=los angeles fc|atlanta united|seattle sounders=seattle sounders fc|columbus crew|fc cincinnati|portland timbers;new york city fc=nycfc|new york red bulls=ny red bulls|orlando city|austin fc|philadelphia union|st louis city|nashville sc|san diego fc\nmex.1:club america=america mexico|chivas guadalajara=guadalajara,chivas|cruz azul|pumas unam=pumas|tigres uanl=tigres|monterrey=rayados monterrey|toluca;leon=club leon|pachuca|santos laguna|atlas guadalajara=atlas|tijuana=xolos tijuana|necaxa|puebla\nmex.2:atlante|leones negros|cancun fc|mineros de zacatecas=mineros zacatecas|celaya|venados fc=venados;correcaminos uat=correcaminos|morelia=atletico morelia|tepatitlan fc=tepatitlan|tapatio|alebrijes de oaxaca=alebrijes\ncol.1:atletico nacional=nacional medellin|millonarios|america de cali|deportivo cali|junior barranquilla=junior|independiente santa fe=santa fe|independiente medellin=deportivo independiente medellin;once caldas|deportes tolima=tolima|deportivo pasto|alianza petrolera=alianza fc|aguilas doradas|bucaramanga=atletico bucaramanga\njpn.1:kashima antlers|vissel kobe|urawa red diamonds=urawa reds|yokohama f marinos=yokohama f. marinos,yokohama marinos|kawasaki frontale|sanfrecce hiroshima|kashiwa reysol|fc tokyo=f.c. tokyo;gamba osaka|cerezo osaka|nagoya grampus|machida zelvia|kyoto sanga|tokyo verdy|shimizu s pulse\nkor.1:jeonbuk hyundai motors=jeonbuk|ulsan hyundai=ulsan hd,ulsan|pohang steelers=pohang|fc seoul=seoul|suwon samsung bluewings=suwon bluewings|incheon united;daejeon hana citizen=daejeon|gwangju fc=gwangju|daegu fc=daegu|gangwon fc=gangwon|jeju united=jeju\nksa.1:al hilal=al hilal saudi|al nassr|al ittihad jeddah=al ittihad|al ahli jeddah=al ahli|al qadsiah=al qadisiya|al shabab riyadh=al shabab;al taawoun|al fateh|al ettifaq|neom sc=neom|al kholood\negy.1:pyramids fc=pyramids|al masry=al masry port said|ismaily sc=ismaily|ceramica cleopatra|modern sport=modern future;enppi|zed fc|smouha|al ittihad alexandria=ittihad alexandria|el gouna|national bank of egypt\nmar.1:far rabat=as far,as far rabat|rs berkane=renaissance berkane,berkane|fus rabat|maghreb fes=mas fes|difaa el jadida|moghreb tetouan;olympique safi|hassania agadir|ittihad tanger=ir tanger|union touarga|chabab mohammedia\nrsa.1:orlando pirates|kaizer chiefs|supersport united|stellenbosch fc=stellenbosch|sekhukhune united|cape town city;amazulu|chippa united|golden arrows|ts galaxy|richards bay fc|polokwane city\nchi.1:colo colo=colo-colo|universidad de chile=la u|universidad catolica|union espanola|palestino|audax italiano;everton vina del mar=everton de vina del mar|cobresal|huachipato|ohiggins=o higgins|nublense\nuru.1:penarol=club atletico penarol|nacional montevideo=club nacional de football|defensor sporting|danubio|liverpool montevideo=liverpool uruguay;montevideo wanderers|cerro largo|plaza colonia|racing montevideo=racing uruguay|boston river\nper.1:universitario de deportes=universitario|alianza lima|sporting cristal|melgar=fbc melgar|cienciano|sport huancayo;cusco fc|deportivo garcilaso|sport boys|atletico grau|comerciantes unidos\npar.1:olimpia asuncion=club olimpia,olimpia|cerro porteno|libertad asuncion=libertad paraguay|guarani asuncion=club guarani|nacional asuncion=nacional paraguay;sportivo luqueno|sol de america|general caballero|sportivo trinidense\nbol.1:bolivar=club bolivar|the strongest|always ready|jorge wilstermann=wilstermann|oriente petrolero|nacional potosi;aurora cochabamba=aurora|blooming|real tomayapo|independiente petrolero\necu.1:ldu quito=liga de quito,liga deportiva universitaria de quito|independiente del valle|barcelona sc guayaquil=barcelona sc|emelec|el nacional quito=el nacional|aucas;deportivo cuenca|universidad catolica quito|mushuc runa|delfin sc|orense sc\nven.1:deportivo tachira|caracas fc=caracas|deportivo la guaira|monagas sc|academia puerto cabello|zamora fc;metropolitanos fc|estudiantes merida=estudiantes de merida|portuguesa fc|carabobo fc\nnga.1:enyimba=enyimba international|rivers united|remo stars|rangers international=enugu rangers|kano pillars|shooting stars sc=3sc;akwa united|plateau united|kwara united|abia warriors|bayelsa united\ngha.1:asante kotoko=kotoko|hearts of oak=accra hearts of oak|medeama sc=medeama|samartex|bechem united|aduana stars;bibiani gold stars=gold stars|dreams fc|nations fc|berekum chelsea|great olympics\nchn.1:shanghai port=shanghai sipg|shanghai shenhua|beijing guoan|shandong taishan=shandong luneng|chengdu rongcheng|zhejiang professional=zhejiang fc;tianjin jinmen tiger|wuhan three towns|henan fc=henan songshan longmen|qingdao west coast\nind.1:mohun bagan super giant=mohun bagan|east bengal=emami east bengal|bengaluru fc|mumbai city fc=mumbai city|fc goa|odisha fc;kerala blasters|chennaiyin fc|hyderabad fc|punjab fc|jamshedpur fc|northeast united\ntha.1:buriram united|bangkok united=true bangkok united|port fc=port thailand|muangthong united|bg pathum united=bangkok glass|chonburi fc;chiangrai united|ratchaburi fc|nakhon ratchasima|pt prachuap\nmys.1:johor darul tazim=jdt,johor dt|selangor fc|kedah darul aman|terengganu fc|sabah fc|sri pahang=pahang fc;kuala lumpur city|penang fc|perak fc|negeri sembilan\nidn.1:persib bandung=persib|persija jakarta=persija|persebaya surabaya=persebaya|bali united|borneo fc samarinda=borneo fc|psm makassar;arema fc|persik kediri|psis semarang|madura united|dewa united\nsgp.1:lion city sailors|tampines rovers|albirex niigata singapore=albirex niigata s|balestier khalsa|geylang international;hougang united|brunei dpmm=dpmm|young lions|tanjong pagar united\naus.1:melbourne city|melbourne victory|sydney fc|western sydney wanderers=ws wanderers|adelaide united|central coast mariners|wellington phoenix;perth glory|brisbane roar|newcastle jets|auckland fc|macarthur fc|western united\nirl.1:shamrock rovers|bohemians dublin=bohemians|st patricks athletic=st patricks|dundalk|derry city|shelbourne;sligo rovers|waterford fc|galway united|drogheda united|cork city\nnor.1:bodo glimt=bodoe glimt,bodø glimt|molde|rosenborg|brann=sk brann|viking stavanger=viking fk|valerenga=valerenga oslo;tromso=tromso il|sarpsborg 08|fredrikstad|lillestrom|stromsgodset\nswe.1:malmo ff=malmo|aik stockholm=aik|djurgardens if=djurgarden|hammarby if=hammarby|ifk goteborg=goteborg|if elfsborg=elfsborg;bk hacken=hacken|ifk norrkoping=norrkoping|mjallby aif=mjallby|kalmar ff\nden.1:fc copenhagen=kobenhavn,fc kobenhavn|brondby if=brondby|fc midtjylland=midtjylland|nordsjaelland=fc nordsjaelland|aarhus gf=agf aarhus|randers fc=randers;silkeborg|viborg ff=viborg|odense bk=ob odense|aalborg bk=aalborg\naut.1:red bull salzburg=rb salzburg|sturm graz=sk sturm graz|rapid vienna=rapid wien|austria vienna=austria wien|lask linz=lask|wolfsberger ac=wolfsberger;hartberg=tsv hartberg|blau weiss linz|grazer ak=gak|ried=sv ried\ngre.1:olympiacos=olympiakos|panathinaikos|aek athens=aek|paok thessaloniki=paok|aris thessaloniki=aris|atromitos;asteras tripolis=asteras aktor|ofi crete=ofi|panetolikos|volos nfc=volos\ncyp.1:apoel nicosia=apoel|omonia nicosia=omonia|pafos fc=pafos|apollon limassol=apollon|anorthosis famagusta=anorthosis|aek larnaca;aris limassol|nea salamina|ethnikos achna|enosis neon paralimni\nrus.1:zenit saint petersburg=zenit st petersburg,zenit|spartak moscow=spartak moskva|cska moscow=cska moskva|lokomotiv moscow=lokomotiv moskva|dynamo moscow=dynamo moskva|krasnodar;rubin kazan|rostov=fc rostov|akhmat grozny=akhmat|krylia sovetov|baltika kaliningrad\nusa.usl.1:louisville city fc=louisville city|tampa bay rowdies|sacramento republic=sacramento republic fc|new mexico united|charleston battery|oakland roots;phoenix rising|san antonio fc|detroit city fc=detroit city|indy eleven|pittsburgh riverhounds\nusa.usl.l1:richmond kickers|union omaha|forward madison|one knoxville sc|greenville triumph|south georgia tormenta;chattanooga red wolves|spokane velocity|charlotte independence|central valley fuego\neng.w.1:chelsea women=chelsea|arsenal women=arsenal|manchester city women=man city,manchester city|manchester united women=man utd,manchester united|liverpool women=liverpool|tottenham hotspur women=tottenham,spurs|aston villa women=aston villa;brighton women=brighton|everton women=everton|west ham women=west ham|leicester city women=leicester|crystal palace women=crystal palace\nesp.w.1:barcelona femeni=barcelona,fc barcelona femeni|real madrid femenino=real madrid|atletico madrid femenino=atletico madrid|real sociedad femenino=real sociedad|athletic club femenino=athletic club;madrid cff|sevilla femenino=sevilla|deportivo la coruna feminino=deportivo la coruna|levante feminino=levante|tenerife women=udg tenerife\nfra.w.1:ol lyonnes=olympique lyonnais feminine|psg feminin=paris saint germain feminin,paris sg|paris fc feminin=paris fc|fc fleury 91=fleury 91|montpellier feminin=montpellier;nantes feminin=fc nantes|bordeaux feminine=bordeaux|saint etienne feminine=saint etienne|dijon fco feminin=dijon\nusa.nwsl:portland thorns|orlando pride|gotham fc=nj ny gotham fc|washington spirit|kansas city current=kc current|san diego wave|north carolina courage=nc courage|angel city fc=angel city;seattle reign=ol reign|houston dash|chicago stars=chicago red stars|racing louisville|bay fc|utah royals|boston legacy|denver summit\nusa.w.usl.1:carolina ascent|dc power fc|spokane zephyr|tampa bay sun|fort lauderdale united|dallas trinity;lexington sc women|brooklyn fc women|sporting jax women|palm beach royal\ncan.w.nsl:afc toronto=toronto afc|vancouver rise|montreal roses=roses de montreal|ottawa rapid;calgary wild|halifax tides\naus.w.1:melbourne city women=melbourne city|melbourne victory women=melbourne victory|sydney fc women=sydney fc|western united women=western united|brisbane roar women=brisbane roar;adelaide united women=adelaide united|canberra united|perth glory women=perth glory|newcastle jets women=newcastle jets|wellington phoenix women=wellington phoenix"

COUNTRY_CUPS = {
    "eng.fa":"eng.1","eng.league_cup":"eng.1","eng.trophy":"eng.3",
    "ger.dfb_pokal":"ger.1","esp.copa_del_rey":"esp.1",
    "ita.coppa_italia":"ita.1","fra.coupe_de_france":"fra.1",
    "arg.copa":"arg.1","usa.open":"usa.1",
}
PROVIDER_CODES = {
    "PL":"eng.1","OF:EN.1":"eng.1","PD":"esp.1","OF:ES.1":"esp.1",
    "BL1":"ger.1","OF:DE.1":"ger.1","OL:BL1":"ger.1",
    "SA":"ita.1","OF:IT.1":"ita.1","FL1":"fra.1","OF:FR.1":"fra.1",
    "PPL":"por.1","OF:PT.1":"por.1","DED":"ned.1","OF:NL.1":"ned.1",
    "BSA":"bra.1","ELC":"eng.2","OF:EN.2":"eng.2",
    "OL:BL2":"ger.2","OL:BL3":"ger.2",
}
WOMENS_LEAGUES = frozenset({
    "eng.w.1","esp.w.1","fra.w.1","usa.nwsl",
    "usa.w.usl.1","can.w.nsl","aus.w.1",
})


def parse_catalog(raw=RAW_CATALOG):
    catalog={}
    for line in raw.strip().splitlines():
        code,data=line.split(":",1)
        if code in catalog or not code:
            raise ValueError("Duplicate league identity: "+code)
        tiers=data.split(";")
        if len(tiers)!=2:
            raise ValueError("Two editorial recognition tiers needed: "+code)
        catalog[code]=tuple(
            [(name.split("=",1)[0].strip(),score,
              tuple(n.strip() for n in name.split("=",1)[1].split(","))
              if "=" in name else ())
             for name in group.split("|") if name]
            for group,score in zip(tiers,(29,21)))
    return catalog


WORLD_CLUBS=parse_catalog()


def normalize_scope(code):
    code=str(code).upper()
    if code in PROVIDER_CODES:
        return PROVIDER_CODES[code]
    code=code.removeprefix("ES:").lower()
    return COUNTRY_CUPS.get(code,code)


def _indexes(normalize):
    local={}
    all_names={}
    countries={}
    women_names={}
    for code,tiers in WORLD_CLUBS.items():
        local[code]={}
        gender="women" if code in WOMENS_LEAGUES else "senior"
        for group in tiers:
            for canonical,score,aliases in group:
                for raw in (canonical,*aliases):
                    name=normalize(raw)
                    if not name:
                        raise ValueError("Empty club alias")
                    old=local[code].get(name)
                    if old is not None and old[0]!=canonical:
                        raise ValueError(f"Conflicting club alias {code}: {name}")
                    local[code][name]=(canonical,score)
                    entry=(canonical,score,code)
                    all_names.setdefault(name,set()).add(entry)
                    countries.setdefault((gender,code.split(".",1)[0],name),set()).add(entry)
                    if gender=="women":
                        women_names.setdefault(name,set()).add(entry)
    def unique(rows):
        results={}
        for k,entries in rows.items():
            if len({entry[0] for entry in entries})==1:
                canonical,score,_=max(entries,key=lambda value:value[1])
                results[k]=(canonical,score)
        return results
    return local,unique(all_names),unique(countries),unique(women_names)


_CACHE={}
def _index(normalize):
    if normalize not in _CACHE:
        _CACHE[normalize]=_indexes(normalize)
    return _CACHE[normalize]


def recognize_club(text, competition, *, normalize, women=False):
    """Find a known team by exact alias, not substring or another league's name.

    For promotions, search other divisions in the same country. Continental
    cups may look up globally unique aliases. Women's squads never inherit
    male club scores from this registry.
    """
    local,world,country,womens=_index(normalize)
    code=normalize_scope(competition)
    if code in local:
        item=local[code].get(text)
        if item:
            return item
    gender="women" if women else "senior"
    nation=code.split(".",1)[0]
    if (gender,nation,text) in country:
        return country[(gender,nation,text)]
    if women:
        return womens.get(text)
    return world.get(text)
