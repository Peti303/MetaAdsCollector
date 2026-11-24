"""Excel kimenet: Osszesito, 3 Aktiv + 3 Multbeli ful, Kiszurt, Hirdetesek."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import beallitasok as B
from gyujto import Ceg, ablakban, futasi_nap, hirdetes_szoveg
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FEJLEC_KITOLTES = PatternFill("solid", fgColor="1F4E78")
HIVO_KITOLTES = PatternFill("solid", fgColor="FFF2CC")
FEJLEC_BETU = Font(bold=True, color="FFFFFF")

CEG_OSZLOPOK: list[tuple[str, int]] = [
    ("Helyezés", 9), ("Cégnév", 32), ("Telefon", 18), ("További telefonok", 22), ("E-mail", 30),
    ("Weboldal", 30), ("Facebook-oldal", 34), ("Instagram", 18), ("Kategória", 24), ("Szakma", 20),
    ("Pontszám", 10), ("Össz. egyedi elérés", 16), ("Legnagyobb elérés", 15), ("Elérés lekérve (db hirdetés)", 14),
    ("Hirdetések (3 hó)", 12), ("Egyedi kreatív", 11), ("Most aktív hirdetés", 12), ("Friss (<14 nap) aktív is", 13),
    ("Leghosszabb futás (nap)", 13), ("Össz. futási nap", 12), ("Első hirdetés", 12), ("Utolsó aktivitás", 12),
    ("Weboldal pont (100)", 11), ("Weboldal: teljesült szempontok", 40), ("Weboldal aktivitás", 36),
    ("Példa hirdetésszöveg", 60), ("Hirdetéstár", 40),
    ("Hívva (dátum)", 13), ("Eredmény", 18), ("Visszahívás", 13), ("Megjegyzés", 40),
]
HIVO_OSZLOPOK = 4


def _fejlec(ws: Any, oszlopok: list[tuple[str, int]], hivo: int = 0) -> None:
    ws.append([n for n, _ in oszlopok])
    for i, (_, w) in enumerate(oszlopok, 1):
        cella = ws.cell(row=1, column=i)
        cella.font = FEJLEC_BETU
        cella.fill = FEJLEC_KITOLTES
        cella.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    for i in range(len(oszlopok) - hivo + 1, len(oszlopok) + 1):
        ws.cell(row=1, column=i).fill = PatternFill("solid", fgColor="BF8F00")
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 42


def _ceg_sor(c: Ceg, helyezes: int, ma: datetime) -> list[Any]:
    m = c.mutatok(ma)
    tel, em = c.kontaktok()
    pelda = ""
    for a in sorted(c.ablak(ma), key=lambda a: futasi_nap(a, ma) or 0, reverse=True):
        pelda = hirdetes_szoveg(a)
        if pelda:
            break
    web = c.web or {}
    return [
        helyezes, c.nev, tel[0] if tel else "nincs", ", ".join(tel[1:]), ", ".join(em[:3]),
        web.get("weboldal") or (f"https://{c.weboldal_domain()}" if c.weboldal_domain() else ""),
        f"https://www.facebook.com/{c.page_id}", c.instagram or "", c.kategoria or "",
        ", ".join(sorted(c.szakmak)), c.pont, m["ossz_eleres"], m["max_eleres"], len(c.eleresek),
        m["db"], m["kreativ_db"], m["aktiv_db"], "igen" if m["friss_aktiv"] else "",
        m["max_nap"], m["ossz_nap"], m["elso"], m["utolso"],
        web.get("pont"), web.get("pont_reszletek", ""),
        web.get("aktivitas", "") if c.web else ("nincs weboldal (csak Facebook)" if not c.weboldal_domain() else ""),
        pelda[:500],
        f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=HU&view_all_page_id={c.page_id}",
        "", "", "", "",
    ]


def excel_iras(fajl: Path, cegek: list[Ceg], kizart: list[Ceg], ma: datetime, meta: dict[str, Any]) -> None:
    wb = Workbook()
    ossz = wb.active
    ossz.title = "Összesítő"
    sorok: list[tuple[str, Any]] = list(meta.items()) + [
        ("Visszatekintés (lejárt hirdetések)", f"{B.VISSZATEKINTES_NAP} nap"),
        ("Minimális futási idő", f"{B.MIN_FUTAS_NAP} nap"),
        ("Pontozás súlyai", f"elérés {B.SULY_ELERES:.0%}, futási nap {B.SULY_FUTASI_NAP:.0%}, "
                            f"hirdetésszám {B.SULY_HIRDETES_DB:.0%} (relatív, csoporton belül)"),
        ("Szintek", f"felső {B.KIEMELT_ARANY:.0%} Kiemelt, következő {B.KOZEPES_ARANY:.0%} Közepes, többi Kicsi"),
        ("Kulcsszavak", "; ".join(f"{k}: {', '.join(v)}" for k, v in B.KULCSSZAVAK.items())),
        ("", ""),
    ]
    for csop in ("Aktív", "Múltbeli"):
        for szint in ("Kiemelt", "Közepes", "Kicsi"):
            db = sum(1 for c in cegek if c.csoport == csop and c.szint == szint)
            sorok.append((f"{csop} – {szint}", db))
    telefonos = sum(1 for c in cegek if c.kontaktok()[0])
    sorok += [("Elfogadott cégek összesen", len(cegek)), ("ebből telefonszámmal", telefonos),
              ("ebből e-maillel", sum(1 for c in cegek if c.kontaktok()[1])), ("Kiszűrt cégek", len(kizart)),
              ("", ""),
              ("Csoportok", "Aktív: van legalább 14 napja futó aktív hirdetése. Múltbeli: nincs ilyen, de az "
                            "elmúlt 3 hónapban volt legalább 14 napig futott hirdetése (friss aktív hirdetése lehet)."),
              ("Elérés", "A Meta által közölt egyedi fiókos EU-s elérés, cégenként a leghosszabban futó "
                         f"legfeljebb {B.MAX_ELERES_LEKERES_PER_CEG} hirdetésre összeadva.")]
    for k, v in sorok:
        ossz.append([k, v])
    ossz.column_dimensions["A"].width = 36
    ossz.column_dimensions["B"].width = 110
    for r in ossz.iter_rows(min_col=1, max_col=1):
        r[0].font = Font(bold=True)

    for csop in ("Aktív", "Múltbeli"):
        for szint in ("Kiemelt", "Közepes", "Kicsi"):
            ws = wb.create_sheet(f"{csop} – {szint}")
            _fejlec(ws, CEG_OSZLOPOK, HIVO_OSZLOPOK)
            lista = [c for c in cegek if c.csoport == csop and c.szint == szint]
            lista.sort(key=lambda c: c.pont, reverse=True)
            for i, c in enumerate(lista, 1):
                ws.append(_ceg_sor(c, i, ma))
                for col in range(len(CEG_OSZLOPOK) - HIVO_OSZLOPOK + 1, len(CEG_OSZLOPOK) + 1):
                    ws.cell(row=i + 1, column=col).fill = HIVO_KITOLTES
            ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Kiszűrt")
    _fejlec(ws, [("Cégnév", 34), ("Ok", 50), ("Kategória", 26), ("Facebook-oldal", 36), ("Hirdetéstár", 40)])
    for c in kizart:
        ws.append([c.nev, c.kizaras, c.kategoria or "", f"https://www.facebook.com/{c.page_id}",
                   f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=HU"
                   f"&view_all_page_id={c.page_id}"])
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Hirdetések")
    _fejlec(ws, [("Cégnév", 30), ("Csoport", 10), ("Aktív", 7), ("Kezdés", 11), ("Vége", 11), ("Futás (nap)", 9),
                 ("Egyedi elérés", 13), ("Gomb", 14), ("Link", 40), ("Szöveg", 70), ("Hirdetés a Hirdetéstárban", 40)])
    for c in cegek:
        for a in sorted(c.ablak(ma), key=lambda a: futasi_nap(a, ma) or 0, reverse=True):
            if not ablakban(a, ma):
                continue
            ws.append([
                c.nev, c.csoport, "igen" if a.is_active else "nem",
                a.delivery_start_time.date().isoformat() if a.delivery_start_time else "",
                a.delivery_stop_time.date().isoformat() if (a.delivery_stop_time and not a.is_active) else "",
                futasi_nap(a, ma), c.eleresek.get(a.id),
                ", ".join(sorted({cr.cta_type for cr in a.creatives if cr.cta_type})),
                next((cr.link_url for cr in a.creatives if cr.link_url), ""),
                hirdetes_szoveg(a)[:500], f"https://www.facebook.com/ads/library/?id={a.id}",
            ])
    ws.auto_filter.ref = ws.dimensions
    wb.save(fajl)
