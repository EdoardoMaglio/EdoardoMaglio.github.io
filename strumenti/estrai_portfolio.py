"""Estrae materiale dal vecchio portfolio in PDF (export del sito Figma).

Il PDF NON va copiato nel repository: lo script lo legge dal suo percorso.
Il percorso si passa con --pdf, oppure si scrive in materiale/percorso-pdf.txt
(cartella esclusa da Git), oppure nella variabile d'ambiente PORTFOLIO_PDF.

Uso:
  python strumenti/estrai_portfolio.py --anteprime          # PNG ~480 px in _tmp/anteprime/
  python strumenti/estrai_portfolio.py --immagini           # immagini incorporate in _tmp/immagini/
  python strumenti/estrai_portfolio.py --link               # _tmp/link.csv (pagina, url, testo vicino)
  python strumenti/estrai_portfolio.py --testo              # _tmp/testo/pNNN.txt, testo di ogni pagina
  python strumenti/estrai_portfolio.py --esporta p12 reunion
        → rasterizza la pagina 12 (max 1920 px) in src/assets/progetti/reunion/
  python strumenti/estrai_portfolio.py --esporta p12-i03 reunion
        → esporta l'immagine incorporata n. 3 della pagina 12 (max 1920 px)
  python strumenti/estrai_portfolio.py --esporta p12 reunion --ritaglio 0.5,0,1,1
        → solo la metà destra della pagina (frazioni x0,y0,x1,y1)

Richiede PyMuPDF:  python -m pip install --user pymupdf
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

import pymupdf

RADICE = Path(__file__).resolve().parent.parent
TMP = RADICE / "_tmp"
ASSETS = RADICE / "src" / "assets" / "progetti"
LARGHEZZA_ANTEPRIMA = 480
LARGHEZZA_MAX = 1920
LATO_MIN_IMMAGINE = 120  # scarta icone e decorazioni
# Pagine con dati personali (telefono, data di nascita): mai esportarle nel sito.
PAGINE_RISERVATE = {66, 74}


def trova_pdf(arg: str | None) -> Path:
    candidati = [arg, os.environ.get("PORTFOLIO_PDF")]
    file_percorso = RADICE / "materiale" / "percorso-pdf.txt"
    if file_percorso.exists():
        candidati.append(file_percorso.read_text(encoding="utf-8").strip())
    for c in candidati:
        if c and Path(c).is_file():
            return Path(c)
    sys.exit(
        "PDF non trovato: usa --pdf <percorso>, PORTFOLIO_PDF o materiale/percorso-pdf.txt"
    )


def rasterizza(pagina: pymupdf.Page, larghezza: int, clip: pymupdf.Rect | None = None) -> pymupdf.Pixmap:
    area = clip or pagina.rect
    zoom = larghezza / area.width
    return pagina.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)


def anteprime(doc: pymupdf.Document) -> None:
    out = TMP / "anteprime"
    out.mkdir(parents=True, exist_ok=True)
    for i, pagina in enumerate(doc, start=1):
        rasterizza(pagina, LARGHEZZA_ANTEPRIMA).save(out / f"p{i:03d}.png")
    print(f"{len(doc)} anteprime in {out}")


def immagini(doc: pymupdf.Document) -> None:
    out = TMP / "immagini"
    out.mkdir(parents=True, exist_ok=True)
    viste: dict[int, str] = {}
    righe = []
    for i, pagina in enumerate(doc, start=1):
        for n, info in enumerate(pagina.get_images(full=True), start=1):
            xref = info[0]
            nome = f"p{i:03d}-i{n:02d}"
            if xref in viste:  # stessa immagine riusata su più pagine
                righe.append((nome, "", "", f"uguale a {viste[xref]}"))
                continue
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n - pix.alpha > 3:  # CMYK → RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            if min(pix.width, pix.height) < LATO_MIN_IMMAGINE:
                continue
            viste[xref] = nome
            pix.save(out / f"{nome}.png")
            righe.append((nome, pix.width, pix.height, ""))
    with open(out / "_indice.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["immagine", "larghezza", "altezza", "nota"])
        w.writerows(righe)
    print(f"{len(viste)} immagini in {out} (indice in _indice.csv)")


def testo_vicino(pagina: pymupdf.Page, rect: pymupdf.Rect, margine: float = 40) -> str:
    area = pymupdf.Rect(rect.x0 - margine, rect.y0 - margine, rect.x1 + margine, rect.y1 + margine)
    parole = [w[4] for w in pagina.get_text("words") if pymupdf.Rect(w[:4]).intersects(area)]
    return re.sub(r"\s+", " ", " ".join(parole)).strip()[:200]


def link(doc: pymupdf.Document) -> None:
    TMP.mkdir(exist_ok=True)
    out = TMP / "link.csv"
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pagina", "url", "testo_vicino"])
        for i, pagina in enumerate(doc, start=1):
            for l in pagina.get_links():
                if l.get("kind") == pymupdf.LINK_URI and l.get("uri"):
                    w.writerow([i, l["uri"], testo_vicino(pagina, l["from"])])
                    n += 1
    print(f"{n} link in {out}")


def testo(doc: pymupdf.Document) -> None:
    out = TMP / "testo"
    out.mkdir(parents=True, exist_ok=True)
    for i, pagina in enumerate(doc, start=1):
        (out / f"p{i:03d}.txt").write_text(pagina.get_text(sort=True), encoding="utf-8")
    print(f"testo di {len(doc)} pagine in {out}")


def esporta(doc: pymupdf.Document, codice: str, slug: str, ritaglio: str | None) -> None:
    m = re.fullmatch(r"p(\d+)(?:-i(\d+))?", codice)
    if not m:
        sys.exit("Codice non valido: usa p12 (pagina) o p12-i03 (immagine)")
    n_pag = int(m.group(1))
    if not 1 <= n_pag <= len(doc):
        sys.exit(f"Pagina {n_pag} inesistente (il PDF ne ha {len(doc)})")
    if n_pag in PAGINE_RISERVATE:
        sys.exit(f"Pagina {n_pag} riservata (contiene dati personali): esportazione bloccata")
    pagina = doc[n_pag - 1]
    out = ASSETS / slug
    out.mkdir(parents=True, exist_ok=True)

    if m.group(2):
        n_img = int(m.group(2))
        lista = pagina.get_images(full=True)
        if not 1 <= n_img <= len(lista):
            sys.exit(f"La pagina {n_pag} ha {len(lista)} immagini")
        pix = pymupdf.Pixmap(doc, lista[n_img - 1][0])
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.width > LARGHEZZA_MAX:
            fattore = LARGHEZZA_MAX / pix.width
            pix = pymupdf.Pixmap(pix, LARGHEZZA_MAX, round(pix.height * fattore), None)
        dest = out / f"{codice}.png"
    else:
        clip = None
        if ritaglio:
            x0, y0, x1, y1 = (float(v) for v in ritaglio.split(","))
            r = pagina.rect
            clip = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                                r.x0 + x1 * r.width, r.y0 + y1 * r.height)
        pix = rasterizza(pagina, LARGHEZZA_MAX if clip is None else min(LARGHEZZA_MAX, round(clip.width * 2)), clip)
        suffisso = "" if not ritaglio else "-r" + ritaglio.replace(",", "_").replace(".", "")
        dest = out / f"{codice}{suffisso}.png"
    pix.save(dest)
    print(f"{dest.relative_to(RADICE)}  ({pix.width}×{pix.height})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", help="percorso del PDF del vecchio portfolio")
    ap.add_argument("--anteprime", action="store_true")
    ap.add_argument("--immagini", action="store_true")
    ap.add_argument("--link", action="store_true")
    ap.add_argument("--testo", action="store_true")
    ap.add_argument("--esporta", nargs=2, metavar=("CODICE", "SLUG"))
    ap.add_argument("--ritaglio", help="frazioni x0,y0,x1,y1 della pagina (solo con --esporta pNN)")
    a = ap.parse_args()
    if not any([a.anteprime, a.immagini, a.link, a.testo, a.esporta]):
        ap.print_help()
        return
    doc = pymupdf.open(trova_pdf(a.pdf))
    if a.anteprime:
        anteprime(doc)
    if a.immagini:
        immagini(doc)
    if a.link:
        link(doc)
    if a.testo:
        testo(doc)
    if a.esporta:
        esporta(doc, *a.esporta, a.ritaglio)


if __name__ == "__main__":
    main()
