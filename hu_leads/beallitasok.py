"""A gyujto allithato beallitasai. Itt modosithatod a szabalyokat kod nelkul."""

# --- Celszamok -------------------------------------------------------------
CEL_AKTIV = 30  # ennyi ceg kell az "Aktiv" csoportba
CEL_MULTBELI = 30  # ennyi ceg kell a "Multbeli" csoportba

# --- Idoszabalyok ----------------------------------------------------------
MIN_FUTAS_NAP = 14  # legalabb ennyi napig kell futnia egy hirdetesnek
VISSZATEKINTES_NAP = 90  # lejart hirdetesek: ennyi napon belul kellett vegzodniuk

# --- Kulcsszavak szakmankent ------------------------------------------------
KULCSSZAVAK = {
    "Burkolás": ["burkolás", "burkoló", "csempézés", "járólap"],
    "Szigetelés": ["szigetelés", "hőszigetelés", "homlokzati szigetelés", "padlásfödém szigetelés"],
    "Gipszkarton": ["gipszkarton", "gipszkartonozás", "szárazépítés", "álmennyezet"],
}

# Kulcsszavankent legfeljebb ennyi hirdetes (30-asaval kerjuk le)
MAX_AKTIV_HIRDETES_PER_KULCSSZO = 90
MAX_LEJART_HIRDETES_PER_KULCSSZO = 240
# Cegenkent legfeljebb ennyi hirdetest kerunk le a teljes kephez
MAX_HIRDETES_PER_CEG = 60
# Cegenkent legfeljebb ennyi hirdetes elereset kerjuk le (hirdetesenkent 1 keres)
MAX_ELERES_LEKERES_PER_CEG = 4

# --- Pontozas (relativ, a csoporton belul) ---------------------------------
SULY_ELERES = 0.60
SULY_FUTASI_NAP = 0.25
SULY_HIRDETES_DB = 0.15
# Szintek: a legjobb 20% Kiemelt, a kovetkezo 30% Kozepes, a tobbi Kicsi
KIEMELT_ARANY = 0.20
KOZEPES_ARANY = 0.30

# --- Kategoria-szures ------------------------------------------------------
# A Facebook-oldal kategoriajaban keresett szoreszletek (kisbetusen).
# Ha barmelyik TILTOTT szerepel, a ceg kiesik. Kulonben kell egy ENGEDELYEZETT.
ENGEDELYEZETT_KATEGORIAK = [
    "construction", "contractor", "entrepreneur", "home improvement", "renovation",
    "tiling", "tile", "flooring", "insulation", "drywall", "plaster", "local business",
    "home service", "handyman", "roofing", "painting", "carpenter", "builder", "interior design",
    "építő", "kivitelez", "felújít", "burkol", "szigetel", "vállalkoz", "szaki",
]
TILTOTT_KATEGORIAK = [
    "building material", "real estate", "lawyer", "law firm", "shopping", "retail", "store",
    "e-commerce", "website", "bank", "financ", "furniture", "hardware", "media", "news",
    "education", "school", "wholesale", "manufactur",
    "építőanyag", "ingatlan", "ügyvéd", "bolt", "áruház", "webáruház", "nagyker",
]
# Ilyen gombu hirdetes eseten a ceg kiesik (bolt / webaruhaz)
TILTOTT_CTA = {"SHOP_NOW"}

# --- Kimeles az IP vedelmeert -----------------------------------------------
META_SZUNET = (5.0, 9.0)  # masodperc ket Meta-keres kozott (veletlenszeru)
HOSSZU_SZUNET_GYAKORISAG = (20, 30)  # ennyi keresenkent hosszabb szunet
HOSSZU_SZUNET = (60.0, 180.0)  # masodperc
KORLATOZAS_VARAKOZAS = 600  # ha a Meta korlatoz: ennyit var, majd egyszer ujraprobal
WEB_SZUNET = (2.0, 5.0)  # masodperc ket weboldal-keres kozott
WEB_MAX_OLDAL = 4  # cegenkent ennyi aloldalt nez meg
WEB_TIMEOUT = 15
