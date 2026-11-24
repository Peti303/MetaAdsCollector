"""Adatellenorzo probafutas (1. lepes).

Kis mintat kerdez le a Meta Hirdetestarbol (HU, aktiv + lejart hirdetesek),
es megnezi, hogy a kesobbi gyujteshez szukseges adatok elerhetok-e:
lejart hirdetesek befejezesi datuma, futasi ido, egyedi fiokos eleres.
Az eredmeny a proba_eredmeny.txt fajlba kerul, ezt kell visszakuldeni.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from meta_ads_collector import MetaAdsCollector

KULCSSZAVAK = ["burkolás", "szigetelés", "gipszkarton"]
HIRDETES_PER_KULCSSZO = 30
RESZLETEZETT_PER_KULCSSZO = 3
OUT_DIR = Path(__file__).resolve().parent
PHONE_RE = re.compile(r"(?:\+36|06)[\s\-/]?\(?\d{1,2}\)?[\s\-/]?\d{3}[\s\-]?\d{3,4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def pihen(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))


def nap(ad, most):
    if ad.delivery_start_time is None:
        return None
    vege = most if ad.is_active else ad.delivery_stop_time
    if vege is None:
        return None
    start = ad.delivery_start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if vege.tzinfo is None:
        vege = vege.replace(tzinfo=timezone.utc)
    return (vege - start).days


def main() -> int:
    most = datetime.now(timezone.utc)
    sorok: list[str] = [f"Probafutas: {most.isoformat(timespec='seconds')}", ""]
    nyers = open(OUT_DIR / "proba_nyers.jsonl", "w", encoding="utf-8")
    ossz_ok = True

    with MetaAdsCollector(rate_limit_delay=5.0, jitter=4.0, max_retries=2) as col:
        for kw in KULCSSZAVAK:
            sorok.append(f"=== Kulcsszo: {kw} ===")
            ads = []
            try:
                for ad in col.search(query=kw, country="HU", status="ALL",
                                     max_results=HIRDETES_PER_KULCSSZO, page_size=30):
                    ads.append(ad)
            except Exception as exc:  # noqa: BLE001
                ossz_ok = False
                sorok.append(f"HIBA a keresesnel: {type(exc).__name__}: {exc}")
            aktiv = [a for a in ads if a.is_active]
            lejart = [a for a in ads if a.is_active is False]
            lejart_datummal = [a for a in lejart if a.delivery_stop_time]
            utolso30 = [a for a in lejart_datummal
                        if (most - a.delivery_stop_time.replace(tzinfo=a.delivery_stop_time.tzinfo or timezone.utc)).days <= 30]
            napok = [nap(a, most) for a in ads]
            min14 = [d for d in napok if d is not None and d >= 14]
            oldalak = {a.page.id for a in ads if a.page}
            linkes = [a for a in ads if any(c.link_url for c in a.creatives)]
            telefon = [a for a in ads if any(PHONE_RE.search(c.body or "") for c in a.creatives)]
            email = [a for a in ads if any(EMAIL_RE.search(c.body or "") for c in a.creatives)]
            sorok += [
                f"Hirdetesek: {len(ads)} | aktiv: {len(aktiv)} | lejart: {len(lejart)} | ismeretlen: {len(ads)-len(aktiv)-len(lejart)}",
                f"Lejart, befejezesi datummal: {len(lejart_datummal)} | ebbol utolso 30 napban vegzodott: {len(utolso30)}",
                f"Futasi ido kiszamolhato: {sum(d is not None for d in napok)} | legalabb 14 napig futott: {len(min14)}",
                f"Kulonbozo hirdeto oldal: {len(oldalak)} | weboldal-linkes: {len(linkes)} | telefon a szovegben: {len(telefon)} | email a szovegben: {len(email)}",
            ]
            # Reszletek (eleres) nehany hirdetesre: a leghosszabban futok
            jeloltek = sorted(ads, key=lambda a: nap(a, most) or -1, reverse=True)[:RESZLETEZETT_PER_KULCSSZO]
            for ad in jeloltek:
                pihen(5, 9)
                try:
                    e = col.enrich_ad(ad)
                except Exception as exc:  # noqa: BLE001
                    e = ad
                    sorok.append(f"  reszletek HIBA {ad.id}: {exc}")
                nev = e.page.name if e.page else "?"
                kat = e.page.category if e.page else None
                link = next((c.link_url for c in e.creatives if c.link_url), None)
                sorok.append(
                    f"  - {nev} | aktiv={e.is_active} | napok={nap(e, most)} | EU eleres={e.eu_total_reach} | "
                    f"kategoria={kat} | cta={next((c.cta_type for c in e.creatives if c.cta_type), None)} | link={link}"
                )
                ads[ads.index(ad)] = e
            for a in ads:
                nyers.write(json.dumps({"kulcsszo": kw, **a.to_dict()}, ensure_ascii=False, default=str) + "\n")
            sorok.append("")
            pihen(20, 40)  # hosszabb szunet kulcsszavak kozott

    nyers.close()
    sorok.append("EREDMENY: " + ("rendben lefutott" if ossz_ok else "volt hiba, lasd fent"))
    (OUT_DIR / "proba_eredmeny.txt").write_text("\n".join(sorok), encoding="utf-8")
    print("\n".join(sorok))
    print(f"\nKesz. Kuldd vissza ezt a fajlt: {OUT_DIR / 'proba_eredmeny.txt'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        (OUT_DIR / "proba_eredmeny.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
        sys.exit(1)
