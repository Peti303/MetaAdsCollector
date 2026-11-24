"""Kivitelezo cegek gyujtese a Meta Hirdetestarbol cold callinghoz.

Folyamat:
1. Felderites: kulcsszavas kereses (kulon aktiv es lejart hirdetesek), HU.
2. Cegenkent: a ceg hirdeteseinek lekerese, csoportba sorolas
   (Aktiv / Multbeli), kategoria-szures, egyedi fiokos eleres lekerese.
3. Weboldal-bejaras: telefon, e-mail, weboldal-minoseg es frissessegi jelek.
4. Relativ pontozas csoporton belul, 3 szint, Excel kimenet.

A beallitasok a beallitasok.py fajlban modosithatok.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import beallitasok as B

from meta_ads_collector import MetaAdsCollector
from meta_ads_collector.exceptions import RateLimitError
from meta_ads_collector.models import Ad

MAPPA = Path(__file__).resolve().parent
TAR = MAPPA / "gyorsitotar"
LOG = logging.getLogger("hu_leads")

PHONE_RE = re.compile(r"(?<![\d])(?:\+\s?36|06)[\s\-/.]*\(?\d{1,2}\)?[\s\-/.]*\d{3}[\s\-/.]*\d{3,4}(?![\d])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
EMAIL_TILTOTT = ("example.", "sentry", "wixpress", "domain.", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
NEM_WEBOLDAL = (
    "facebook.com", "fb.me", "fb.com", "fb.watch", "instagram.com", "wa.me", "whatsapp.com", "m.me",
    "messenger.com", "youtube.com", "youtu.be", "tiktok.com", "google.com", "goo.gl", "forms.gle",
)
KAPCSOLAT_LINK_RE = re.compile(
    r"kapcsolat|elerhetoseg|elérhetőség|impresszum|contact|rolunk|rólunk|ajanlatkeres|ajánlatkérés", re.I
)
A_TAG_RE = re.compile(r"<a\s[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)


class Leallas(Exception):
    """A Meta tartosan korlatoz: a gyujtes leall, az eddigi eredmeny mentesre kerul."""


# ---------------------------------------------------------------------------
# Segedfuggvenyek
# ---------------------------------------------------------------------------

def most() -> datetime:
    return datetime.now(timezone.utc)


def utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def futasi_nap(ad: Ad, ma: datetime) -> int | None:
    if ad.delivery_start_time is None:
        return None
    vege = ma if ad.is_active else ad.delivery_stop_time
    if vege is None:
        return None
    return max(0, (utc(vege) - utc(ad.delivery_start_time)).days)


def ablakban(ad: Ad, ma: datetime) -> bool:
    """Aktiv, vagy az utolso VISSZATEKINTES_NAP napban vegzodott."""
    if ad.is_active:
        return True
    if ad.delivery_stop_time is None:
        return False
    return utc(ad.delivery_stop_time) >= ma - timedelta(days=B.VISSZATEKINTES_NAP)


def telefon_normal(nyers: str) -> str | None:
    d = re.sub(r"\D", "", nyers)
    if d.startswith("36") or d.startswith("06"):
        d = d[2:]
    else:
        return None
    if d.startswith("1") and len(d) == 8:
        return f"+36 1 {d[1:4]} {d[4:]}"
    if len(d) == 9:
        return f"+36 {d[:2]} {d[2:5]} {d[5:]}"
    if len(d) == 8:
        return f"+36 {d[:2]} {d[2:5]} {d[5:]}"
    return None


def telefonok(szoveg: str) -> list[str]:
    ki = []
    for m in PHONE_RE.findall(szoveg or ""):
        t = telefon_normal(m)
        if t and t not in ki:
            ki.append(t)
    return ki


def emailek(szoveg: str) -> list[str]:
    ki = []
    for m in EMAIL_RE.findall(szoveg or ""):
        e = m.lower().strip(".")
        if not any(t in e for t in EMAIL_TILTOTT) and e not in ki:
            ki.append(e)
    return ki


def kibont_link(url: str) -> str:
    """l.facebook.com/l.php?u=... atiranyitas kibontasa."""
    p = urlparse(url)
    if "facebook.com" in p.netloc and p.path.startswith("/l.php"):
        u = parse_qs(p.query).get("u")
        if u:
            return unquote(u[0])
    return url


def domain(url: str) -> str | None:
    try:
        p = urlparse(kibont_link(url))
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    d = p.netloc.lower().split(":")[0]
    d = d[4:] if d.startswith("www.") else d
    if any(d == x or d.endswith("." + x) for x in NEM_WEBOLDAL):
        return None
    return d


def kategoria_dontes(kat: str | None) -> tuple[bool, str]:
    if not kat:
        return False, "kategória nem elérhető"
    k = kat.lower()
    for t in B.TILTOTT_KATEGORIAK:
        if t in k:
            return False, f"kizárt kategória: {kat}"
    for e in B.ENGEDELYEZETT_KATEGORIAK:
        if e in k:
            return True, ""
    return False, f"nem kivitelezői kategória: {kat}"


def cta_tipusok(ad: Ad) -> set[str]:
    return {c.cta_type for c in ad.creatives if c.cta_type}


def hirdetes_szoveg(ad: Ad) -> str:
    return " ".join(filter(None, (x for c in ad.creatives for x in (c.title, c.body, c.description, c.caption))))


def json_ment(nev: str, adat: Any) -> None:
    TAR.mkdir(exist_ok=True)
    tmp = TAR / (nev + ".tmp")
    tmp.write_text(json.dumps(adat, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    tmp.replace(TAR / nev)


def json_tolt(nev: str) -> Any:
    p = TAR / nev
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# Meta-hivasok kimeletes temben
# ---------------------------------------------------------------------------

class Utemezo:
    def __init__(self) -> None:
        self.keresek = 0
        self.kov_hosszu = random.randint(*B.HOSSZU_SZUNET_GYAKORISAG)
        self.sikertelen_reszlet_sorozat = 0

    def szamol(self, db: int = 1) -> None:
        self.keresek += db
        if self.keresek >= self.kov_hosszu:
            s = random.uniform(*B.HOSSZU_SZUNET)
            LOG.info("Hosszabb szunet %.0f mp (eddig %d keres)", s, self.keresek)
            time.sleep(s)
            self.kov_hosszu = self.keresek + random.randint(*B.HOSSZU_SZUNET_GYAKORISAG)

    def szunet(self) -> None:
        time.sleep(random.uniform(*B.META_SZUNET))


def korlatozas_vedett(fn: Callable[[], Any], leiras: str) -> Any:
    """Korlatozasnal var KORLATOZAS_VARAKOZAS mp-et, egyszer ujraprobalja, utana leall."""
    for probalkozas in (1, 2):
        try:
            return fn()
        except RateLimitError:
            if probalkozas == 2:
                raise Leallas(f"A Meta tartósan korlátoz ({leiras}).") from None
            LOG.warning("A Meta korlatoz (%s). Varakozas %d mp, utana egy ujraprobalas.",
                        leiras, B.KORLATOZAS_VARAKOZAS)
            time.sleep(B.KORLATOZAS_VARAKOZAS)
    return None


def kereses(col: MetaAdsCollector, ut: Utemezo, leiras: str, **kw: Any) -> list[Ad]:
    ut.szunet()
    ads = korlatozas_vedett(lambda: list(col.search(country="HU", page_size=30, **kw)), leiras)
    ut.szamol(max(1, (len(ads) + 29) // 30))
    return ads


def reszletek(col: MetaAdsCollector, ut: Utemezo, ad: Ad) -> Ad | None:
    """Egy hirdetes 'See ad details' adatai (eleres, kategoria). None = sikertelen."""
    ut.szunet()
    e = col.enrich_ad(ad)
    ut.szamol()
    if e is ad:  # az enrich_ad hiba eseten az eredetit adja vissza
        ut.sikertelen_reszlet_sorozat += 1
        if ut.sikertelen_reszlet_sorozat >= 3:
            LOG.warning("3 sikertelen reszletlekeres egymas utan: valoszinu korlatozas. Varakozas %d mp.",
                        B.KORLATOZAS_VARAKOZAS)
            time.sleep(B.KORLATOZAS_VARAKOZAS)
            ut.sikertelen_reszlet_sorozat = 0
            e = col.enrich_ad(ad)
            ut.szamol()
            if e is ad:
                raise Leallas("A részletlekérések tartósan sikertelenek (valószínű korlátozás).")
            return e
        return None
    ut.sikertelen_reszlet_sorozat = 0
    return e


# ---------------------------------------------------------------------------
# Weboldal-bejaras
# ---------------------------------------------------------------------------

def web_get(url: str) -> tuple[str | None, str | None, float | None]:
    from curl_cffi import requests as creq

    time.sleep(random.uniform(*B.WEB_SZUNET))
    t0 = time.monotonic()
    try:
        r = creq.get(url, impersonate="chrome", timeout=B.WEB_TIMEOUT, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        LOG.info("Weboldal nem elerheto: %s (%s)", url, type(exc).__name__)
        return None, None, None
    ido = time.monotonic() - t0
    if r.status_code >= 400:
        return None, str(r.url), ido
    ctype = r.headers.get("content-type", "")
    if "html" not in ctype and "xml" not in ctype:
        return None, str(r.url), ido
    return r.text, str(r.url), ido


def weboldal_elemzes(dom: str, ma: datetime) -> dict[str, Any]:
    ered: dict[str, Any] = {"weboldal": f"https://{dom}", "elerheto": False, "telefonok": [], "emailek": [],
                            "pont": None, "pont_reszletek": "", "aktivitas": "", "copyright_ev": None,
                            "oldalterkep_frissitve": None}
    html, vegso, ido = web_get(f"https://{dom}/")
    if html is None:
        html, vegso, ido = web_get(f"http://{dom}/")
    if html is None:
        ered["aktivitas"] = "Weboldal nem elérhető"
        return ered
    ered["elerheto"] = True
    ered["weboldal"] = vegso or ered["weboldal"]
    oldalak = [html]
    alap = vegso or f"https://{dom}/"
    linkek = []
    for href, szoveg in A_TAG_RE.findall(html):
        h = href.strip()
        if h.lower().startswith("tel:"):
            t = telefon_normal(unquote(h[4:]))
            if t and t not in ered["telefonok"]:
                ered["telefonok"].append(t)
            continue
        if h.lower().startswith("mailto:"):
            for e in emailek(unquote(h[7:].split("?")[0])):
                if e not in ered["emailek"]:
                    ered["emailek"].append(e)
            continue
        teljes = urljoin(alap, h)
        cimke = h + " " + re.sub("<[^>]+>", " ", szoveg)
        if (domain(teljes) == domain(alap) and KAPCSOLAT_LINK_RE.search(cimke)
                and teljes not in linkek and teljes.rstrip("/") != alap.rstrip("/")):
            linkek.append(teljes)
    for url in linkek[: B.WEB_MAX_OLDAL - 1]:
        h2, _, _ = web_get(url)
        if h2:
            oldalak.append(h2)
            for href, _ in A_TAG_RE.findall(h2):
                if href.lower().startswith("tel:"):
                    t = telefon_normal(unquote(href[4:]))
                    if t and t not in ered["telefonok"]:
                        ered["telefonok"].append(t)
                elif href.lower().startswith("mailto:"):
                    for e in emailek(unquote(href[7:].split("?")[0])):
                        if e not in ered["emailek"]:
                            ered["emailek"].append(e)
    for o in oldalak:
        szoveg = re.sub(r"<script.*?</script>|<style.*?</style>", " ", o, flags=re.S | re.I)
        szoveg = re.sub(r"<[^>]+>", " ", szoveg)
        for t in telefonok(szoveg):
            if t not in ered["telefonok"]:
                ered["telefonok"].append(t)
        for e in emailek(szoveg):
            if e not in ered["emailek"]:
                ered["emailek"].append(e)

    # --- Minoseg (szabaly alapu, 100 pont) ---
    osszes = " ".join(oldalak)
    kis = html.lower()
    pontok: list[tuple[str, int, bool]] = []
    pontok.append(("HTTPS", 15, (vegso or "").startswith("https://")))
    pontok.append(("mobilbarát", 15, 'name="viewport"' in kis or "name='viewport'" in kis))
    pontok.append(("gyors (<3 mp)", 10, ido is not None and ido < 3))
    pontok.append(("cím+leírás", 10, "<title" in kis and 'name="description"' in kis))
    pontok.append(("űrlap", 10, "<form" in osszes.lower()))
    referencia = re.search(r"referenci|galéri|galeri|munkáink|munkaink|portf", osszes, re.I)
    pontok.append(("referenciák", 10, bool(referencia)))
    pontok.append(("ajánlatkérés", 5, bool(re.search(r"árajánlat|ajánlatkér|arajanlat", osszes, re.I))))
    evek = [int(y) for m in re.findall(r"(?:©|&copy;|copyright)\s*(\d{4})(?:\s*[-–]\s*(\d{4}))?", osszes, re.I)
            for y in m if y]
    evek = [y for y in evek if 2000 <= y <= ma.year]
    cev = max(evek) if evek else None
    ered["copyright_ev"] = cev
    pontok.append(("friss © év", 15, cev is not None and cev >= ma.year - 1))
    lastmod = None
    for sm in ("sitemap.xml", "sitemap_index.xml", "wp-sitemap.xml"):
        x, _, _ = web_get(urljoin(alap, "/" + sm))
        if x and ("<urlset" in x or "<sitemapindex" in x):
            datumok = re.findall(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", x)
            if datumok:
                lastmod = max(datumok)
            break
    ered["oldalterkep_frissitve"] = lastmod
    friss_sm = False
    if lastmod:
        try:
            friss_sm = (ma - datetime.strptime(lastmod, "%Y-%m-%d").replace(tzinfo=timezone.utc)).days <= 180
        except ValueError:
            friss_sm = False
    pontok.append(("oldaltérkép frissítve 180 napon belül", 10, friss_sm))
    ered["pont"] = sum(p for _, p, ok in pontok if ok)
    ered["pont_reszletek"] = ", ".join(n for n, _, ok in pontok if ok) or "-"
    jelek = ["hirdetés ide visz"]
    if cev:
        jelek.append(f"© {cev}")
    if lastmod:
        jelek.append(f"oldaltérkép: {lastmod}")
    ered["aktivitas"] = "; ".join(jelek)
    return ered


# ---------------------------------------------------------------------------
# Ceg-adatok
# ---------------------------------------------------------------------------

@dataclass
class Ceg:
    page_id: str
    nev: str
    szakmak: set[str] = field(default_factory=set)
    hirdetesek: dict[str, Ad] = field(default_factory=dict)
    eleresek: dict[str, int] = field(default_factory=dict)
    kategoria: str | None = None
    instagram: str | None = None
    rolunk: str | None = None
    csoport: str | None = None
    kizaras: str | None = None
    web: dict[str, Any] | None = None
    pont: float = 0.0
    szint: str = ""

    def ablak(self, ma: datetime) -> list[Ad]:
        return [a for a in self.hirdetesek.values() if ablakban(a, ma)]

    def mutatok(self, ma: datetime) -> dict[str, Any]:
        ab = self.ablak(ma)
        napok = [futasi_nap(a, ma) or 0 for a in ab]
        aktiv = [a for a in ab if a.is_active]
        kezd = [utc(a.delivery_start_time) for a in ab if a.delivery_start_time]
        vegek = [ma if a.is_active else utc(a.delivery_stop_time) for a in ab if a.is_active or a.delivery_stop_time]
        friss = any(a.is_active and (futasi_nap(a, ma) or 0) < B.MIN_FUTAS_NAP for a in ab)
        return {
            "db": len(ab),
            "kreativ_db": len({a.collation_id or a.id for a in ab}),
            "aktiv_db": len(aktiv),
            "max_nap": max(napok) if napok else 0,
            "ossz_nap": sum(napok),
            "elso": min(kezd).date().isoformat() if kezd else "",
            "utolso": max(vegek).date().isoformat() if vegek else "",
            "friss_aktiv": friss,
            "ossz_eleres": sum(self.eleresek.values()) if self.eleresek else None,
            "max_eleres": max(self.eleresek.values()) if self.eleresek else None,
        }

    def csoport_dontes(self, ma: datetime) -> str | None:
        ab = self.ablak(ma)
        if any(a.is_active and (futasi_nap(a, ma) or 0) >= B.MIN_FUTAS_NAP for a in ab):
            return "Aktív"
        if any(not a.is_active and (futasi_nap(a, ma) or 0) >= B.MIN_FUTAS_NAP for a in ab):
            return "Múltbeli"
        return None

    def kontaktok(self) -> tuple[list[str], list[str]]:
        tel: list[str] = []
        em: list[str] = []
        forrasok = [hirdetes_szoveg(a) for a in self.hirdetesek.values()] + [self.rolunk or ""]
        for s in forrasok:
            tel += [t for t in telefonok(s) if t not in tel]
            em += [e for e in emailek(s) if e not in em]
        for a in self.hirdetesek.values():
            for c in a.creatives:
                link = (c.link_url or "").lower()
                if "wa.me/" in link or "api.whatsapp.com" in link:
                    t = telefon_normal("+" + re.sub(r"\D", "", link.split("wa.me/")[-1])[:11])
                    if t and t not in tel:
                        tel.append(t)
        if self.web:
            tel += [t for t in self.web.get("telefonok", []) if t not in tel]
            em += [e for e in self.web.get("emailek", []) if e not in em]
        return tel, em

    def weboldal_domain(self) -> str | None:
        c = Counter(d for a in self.hirdetesek.values() for cr in a.creatives
                    if cr.link_url and (d := domain(cr.link_url)))
        return c.most_common(1)[0][0] if c else None


def rangsor(ertekek: list[float | None]) -> list[float]:
    """Relativ helyezes 0..1 (holtversenyben atlagolva). Hianyzo ertek = 0."""
    n = len(ertekek)
    if n <= 1:
        return [1.0] * n
    v = [x if x is not None else -1 for x in ertekek]
    rend = sorted(range(n), key=lambda i: v[i])
    rang = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[rend[j + 1]] == v[rend[i]]:
            j += 1
        for k in range(i, j + 1):
            rang[rend[k]] = (i + j) / 2 / (n - 1)
        i = j + 1
    return [r if ertekek[idx] is not None else 0.0 for idx, r in enumerate(rang)]


def pontozas(cegek: list[Ceg], ma: datetime) -> None:
    m = [c.mutatok(ma) for c in cegek]
    r_el = rangsor([x["ossz_eleres"] for x in m])
    r_nap = rangsor([x["ossz_nap"] for x in m])
    r_db = rangsor([x["db"] for x in m])
    for c, a, b, d in zip(cegek, r_el, r_nap, r_db):
        c.pont = round(100 * (B.SULY_ELERES * a + B.SULY_FUTASI_NAP * b + B.SULY_HIRDETES_DB * d), 1)
    cegek.sort(key=lambda c: c.pont, reverse=True)
    n = len(cegek)
    k1 = max(1, round(n * B.KIEMELT_ARANY)) if n else 0
    k2 = round(n * B.KOZEPES_ARANY)
    for i, c in enumerate(cegek):
        c.szint = "Kiemelt" if i < k1 else ("Közepes" if i < k1 + k2 else "Kicsi")


# ---------------------------------------------------------------------------
# Fo folyamat
# ---------------------------------------------------------------------------

def felderites(col: MetaAdsCollector, ut: Utemezo, ma: datetime) -> dict[str, Ceg]:
    cegek: dict[str, Ceg] = {}
    allapot = json_tolt("felderites_kesz.json") or {}
    # A gyorsitotar 24 oraig ervenyes (ujrainditasnal nem kerdezunk le ujra mindent)
    if not allapot.get("ido") or (ma - datetime.fromisoformat(allapot["ido"])).total_seconds() > 86400:
        allapot = {"ido": ma.isoformat(), "kulcsok": []}
    kesz = allapot["kulcsok"]
    for szakma, szavak in B.KULCSSZAVAK.items():
        for szo in szavak:
            for statusz, maxdb in (("ACTIVE", B.MAX_AKTIV_HIRDETES_PER_KULCSSZO),
                                   ("INACTIVE", B.MAX_LEJART_HIRDETES_PER_KULCSSZO)):
                kulcs = f"{szo}|{statusz}"
                tarfajl = f"felderites_{hashlib.md5(kulcs.encode()).hexdigest()[:10]}.json"
                gyorstar = json_tolt(tarfajl) if kulcs in kesz else None
                if gyorstar is not None:
                    ads = [Ad.from_graphql_response(d) for d in gyorstar]
                else:
                    LOG.info("Kereses: '%s' (%s)", szo, "aktiv" if statusz == "ACTIVE" else "lejart")
                    ads = kereses(col, ut, f"kereses {szo}", query=szo, status=statusz, max_results=maxdb)
                    json_ment(tarfajl, [a.raw_data or {} for a in ads])
                    kesz.append(kulcs)
                    json_ment("felderites_kesz.json", allapot)
                ablakos = 0
                for a in ads:
                    if not a.page or not ablakban(a, ma):
                        continue
                    ablakos += 1
                    c = cegek.setdefault(a.page.id, Ceg(a.page.id, a.page.name))
                    c.szakmak.add(szakma)
                    c.hirdetesek.setdefault(a.id, a)
                LOG.info("  %d hirdetes, ebbol idoablakban: %d | eddigi cegek: %d", len(ads), ablakos, len(cegek))
    return cegek


def elozetes_pont(c: Ceg, ma: datetime) -> float:
    m = c.mutatok(ma)
    return m["ossz_nap"] + 30 * m["db"]


def ceg_feldolgozas(col: MetaAdsCollector, ut: Utemezo, c: Ceg, ma: datetime, tele: dict[str, bool]) -> None:
    # 1. A ceg osszes hirdetese (teljes kep)
    ads = kereses(col, ut, f"ceg {c.nev}", query="", search_type="PAGE", page_ids=[c.page_id],
                  status="ALL", max_results=B.MAX_HIRDETES_PER_CEG)
    for a in ads:
        c.hirdetesek.setdefault(a.id, a)
    if any(cta_tipusok(a) & B.TILTOTT_CTA for a in c.hirdetesek.values()):
        c.kizaras = "bolt / webáruház (Vásárlás gomb)"
        return
    c.csoport = c.csoport_dontes(ma)
    if c.csoport is None:
        c.kizaras = (f"csak friss (<{B.MIN_FUTAS_NAP} nap) aktív hirdetés"
                     if any(a.is_active for a in c.ablak(ma))
                     else f"nincs legalább {B.MIN_FUTAS_NAP} napos hirdetés az időablakban")
        return
    if tele[c.csoport]:
        c.kizaras = f"a(z) {c.csoport} csoport már megtelt"
        return
    # 2. Reszletek: kategoria + eleres a leghosszabban futo hirdetesekre
    jeloltek = sorted(c.ablak(ma), key=lambda a: futasi_nap(a, ma) or 0, reverse=True)
    for i, a in enumerate(jeloltek[: B.MAX_ELERES_LEKERES_PER_CEG]):
        e = reszletek(col, ut, a)
        if e is None:
            if i == 0:
                c.kizaras = "részletek nem kérhetők le (kategória ismeretlen)"
                return
            continue
        c.hirdetesek[a.id] = e
        if e.eu_total_reach is not None:
            c.eleresek[a.id] = e.eu_total_reach
        if e.page:
            c.kategoria = c.kategoria or e.page.category
            c.instagram = c.instagram or e.page.ig_username
            c.rolunk = c.rolunk or e.page.about
            c.nev = e.page.name or c.nev
        if i == 0:
            ok, ok_szoveg = kategoria_dontes(c.kategoria)
            if not ok:
                c.kizaras = ok_szoveg
                return


def futtat() -> int:
    ma = most()
    kezdes = time.monotonic()
    LOG.info("Gyujtes indul: cel %d aktiv + %d multbeli ceg, %d napos visszatekintes",
             B.CEL_AKTIV, B.CEL_MULTBELI, B.VISSZATEKINTES_NAP)
    ut = Utemezo()
    leallas_oka = None
    kesz_cegek: list[Ceg] = []
    kizart: list[Ceg] = []
    with MetaAdsCollector(rate_limit_delay=B.META_SZUNET[0],
                          jitter=B.META_SZUNET[1] - B.META_SZUNET[0], max_retries=2) as col:
        try:
            jeloltek = felderites(col, ut, ma)
            sorrend = []
            for c in jeloltek.values():
                if any(cta_tipusok(a) & B.TILTOTT_CTA for a in c.hirdetesek.values()):
                    c.kizaras = "bolt / webáruház (Vásárlás gomb)"
                    kizart.append(c)
                else:
                    sorrend.append(c)
            sorrend.sort(key=lambda c: elozetes_pont(c, ma), reverse=True)
            LOG.info("Felderites kesz: %d jelolt ceg, %d elozetesen kizarva", len(sorrend), len(kizart))
            darab = {"Aktív": 0, "Múltbeli": 0}
            cel = {"Aktív": B.CEL_AKTIV, "Múltbeli": B.CEL_MULTBELI}
            for i, c in enumerate(sorrend, 1):
                tele = {k: darab[k] >= cel[k] for k in darab}
                if all(tele.values()):
                    break
                # Ha mar a felderitett hirdetesek alapjan Aktiv, es az Aktiv csoport tele: keres nelkul kihagyjuk
                if tele["Aktív"] and c.csoport_dontes(ma) == "Aktív":
                    continue
                LOG.info("[%d/%d] %s (aktiv %d/%d, multbeli %d/%d)", i, len(sorrend), c.nev,
                         darab["Aktív"], cel["Aktív"], darab["Múltbeli"], cel["Múltbeli"])
                ceg_feldolgozas(col, ut, c, ma, tele)
                if c.kizaras:
                    LOG.info("   kizarva: %s", c.kizaras)
                    kizart.append(c)
                else:
                    darab[c.csoport] += 1  # type: ignore[index]
                    kesz_cegek.append(c)
                    LOG.info("   ELFOGADVA: %s | kategoria: %s", c.csoport, c.kategoria)
        except Leallas as exc:
            leallas_oka = str(exc)
            LOG.error("LEALLAS: %s Az eddigi eredmenyek mentese kovetkezik.", exc)

    # 3. Weboldalak
    for i, c in enumerate(kesz_cegek, 1):
        dom = c.weboldal_domain()
        if not dom:
            continue
        LOG.info("Weboldal [%d/%d]: %s", i, len(kesz_cegek), dom)
        try:
            c.web = weboldal_elemzes(dom, ma)
        except Exception as exc:  # noqa: BLE001
            LOG.info("Weboldal-elemzes hiba: %s (%s)", dom, exc)

    # 4. Pontozas es Excel
    for csop in ("Aktív", "Múltbeli"):
        pontozas([c for c in kesz_cegek if c.csoport == csop], ma)
    from excel import excel_iras

    fajl = MAPPA / f"kontaktok_{ma.astimezone().strftime('%Y-%m-%d_%H%M')}.xlsx"
    excel_iras(fajl, kesz_cegek, kizart, ma, {
        "Futás ideje": ma.astimezone().strftime("%Y-%m-%d %H:%M"),
        "Időtartam (perc)": round((time.monotonic() - kezdes) / 60, 1),
        "Meta-kérések (kb.)": ut.keresek,
        "Leállás oka": leallas_oka or "nincs, rendben lefutott",
    })
    LOG.info("KESZ. Excel: %s", fajl)
    return 0 if leallas_oka is None else 2


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(MAPPA / "naplo.txt", encoding="utf-8")],
    )
    for nev in ("meta_ads_collector",):
        logging.getLogger(nev).setLevel(logging.WARNING)
    try:
        return futtat()
    except Exception:  # noqa: BLE001
        LOG.error("Varatlan hiba:\n%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
