"""A gyujto allithato beallitasai. Itt modosithatod a szabalyokat kod nelkul."""

# --- Celszamok -------------------------------------------------------------
CEL_AKTIV = 30  # ennyi ceg kell az "Aktiv" csoportba
CEL_MULTBELI = 30  # ennyi ceg kell a "Multbeli" csoportba
CEL_EGYEB = 20  # rokon szakmak (festo, terkovezo stb.) kulon fulre, a fo csoportok utan

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
# Cegenkent legfeljebb ennyi hirdetes elereset kerjuk le (hirdetesenkent 1 keres)
MAX_ELERES_LEKERES_PER_CEG = 2

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
    "home service", "handyman", "painting", "carpenter", "builder", "interior design",
    "építő", "kivitelez", "felújít", "burkol", "szigetel", "vállalkoz", "szaki",
]
TILTOTT_KATEGORIAK = [
    "building material", "real estate", "lawyer", "law firm", "shopping", "retail", "store",
    "e-commerce", "website", "bank", "financ", "furniture", "hardware", "media", "news",
    "education", "school", "wholesale", "manufactur", "roofing", "advertising", "marketing",
    "építőanyag", "ingatlan", "ügyvéd", "bolt", "áruház", "webáruház", "nagyker",
]
# Ha a ceg hirdeteseinek tobb mint fele ilyen gombos, a ceg kiesik (bolt / webaruhaz)
TILTOTT_CTA = {"SHOP_NOW"}

# --- Szakma-felismeres a hirdetesszovegbol es a cegnevbol (kisbetus szoreszletek) ---
FO_SZAKMA_SZAVAK = ["burkol", "csempé", "csempez", "járólap", "szigetel", "gipszkarton", "szárazépít",
                    "álmennyezet", "hidegburkol"]
TETOFEDO_SZAVAK = ["tetőfed", "tetofed", "bádogos", "cserepes", "tetőcser", "tetőfelújít", "lapostető",
                   "ácsmunk", "ács ", "tetőszerkezet", "cserepeslemez", "trapézlemez"]
EGYEB_SZAKMA_SZAVAK = {
    "festés": ["festés", "festő", "mázol", "tapétáz", "szobafest"],
    "térkövezés": ["térkő", "térkövez", "kőfarag", "díszkő"],
    "nyílászáró": ["ablak", "nyílászáró", "redőny", "ajtó"],
    "alapozás / beton": ["cölöp", "estrich", "esztrich", "beton"],
    "kert / pergola": ["pergola", "terasz", "kerítés"],
    "gépészet / energetika": ["napelem", "hőszivattyú", "klíma", "villany", "fűtés", "víz-gáz"],
}
# Termekertekesitore utalo szavak, illetve szolgaltatasra (kivitelezesre) utalok
TERMEK_SZAVAK = ["webshop", "webáruház", "rendelje", "rendeld", "termék", "forgalmaz", "gyárt", "kapható",
                 "házhozszállít", "kiszállítással", "raktárról", "nagyker", "viszonteladó", "üzletünk",
                 "áruház", "szaküzlet", "katalógus", "rendelés"]
SZOLGALTATAS_SZAVAK = ["vállal", "kivitelez", "árajánlat", "ajánlatkér", "felmérés", "munkáink", "referenci",
                       "szakember", "brigád", "csapatunk", "határidő", "garanciá", "munkadíj", "szerelés"]
# Gyartok, nagy markak, aruhazak: nevben vagy weboldal-cimben
TILTOTT_MARKAK = ["mapei", "sika", "sto ", "stohomlokzat", "knauf", "baumit", "weber", "rigips", "ytong",
                  "wienerberger", "bakonytherm", "austrotherm", "rockwool", "isover", "masterplast", "leier",
                  "fadepo", "maslen", "ceresit", "henkel", "saint-gobain", "obi ", "praktiker", "bauhaus",
                  "bauplaza", "merkbau", "tondach", "bramac", "creaton", "lindab", "kingspan", "schiedel",
                  "porotherm", "xella", "murexin", "kerakoll", "ardex", "zalakerámia", "cersanit", "keravill"]
# E-mail sorrend: ezek elore, az allas/karrier cimek hatra
EMAIL_ELORE = ["info@", "iroda@", "ajanlat@", "office@", "hello@", "kapcsolat@"]
EMAIL_HATRA = ["allas@", "karrier@", "career", "recruit", "hr@", "jobs@", "munka@", "szamlazas@", "noreply"]

# --- Kimeles az IP vedelmeert -----------------------------------------------
META_SZUNET = (5.0, 9.0)  # masodperc ket Meta-keres kozott (veletlenszeru)
HOSSZU_SZUNET_GYAKORISAG = (20, 30)  # ennyi keresenkent hosszabb szunet
HOSSZU_SZUNET = (60.0, 180.0)  # masodperc
KORLATOZAS_VARAKOZAS = 600  # ha a Meta korlatoz: ennyit var, majd egyszer ujraprobal
WEB_SZUNET = (2.0, 5.0)  # masodperc ket weboldal-keres kozott
WEB_MAX_OLDAL = 4  # cegenkent ennyi aloldalt nez meg
WEB_TIMEOUT = 15
