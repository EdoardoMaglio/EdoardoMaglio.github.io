"""Importa nel sito il materiale dei progetti che in sito.yml hanno `tipo: drive`.

Uso:
    python strumenti/importa_drive.py <id-progetto> [<id-progetto> ...]
    python strumenti/importa_drive.py --tutti

Per ogni blocco `- tipo: drive` del progetto:
 1. scarica il file o la cartella pubblica in .importa/<id>/ (fuori dal repository);
 2. converte e ordina:
      immagini -> WebP (lato lungo 1600 px)        -> galleria
      PDF      -> PDF senza metadati + anteprima    -> pdf
      video    -> MP4 H.264 720p + poster           -> video (se <= 25 MB)
      altro    -> elenco «da decidere»
    I file pubblicati si chiamano <id>-01.webp, <id>.pdf...: mai il nome originale,
    che può contenere matricole o dati personali.
 3. riscrive in contenuti/sito.yml il blocco drive con i blocchi galleria / pdf / video;
    se il progetto non ha un'immagine, usa la prima immagine importata.
 4. stampa un riepilogo.

Serve: pip install gdown pillow pymupdf pyyaml, e ffmpeg nel PATH.
"""
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import gdown
import pymupdf
import yaml
from PIL import Image, ImageOps

RADICE = Path(__file__).resolve().parent.parent
SITO = RADICE / 'contenuti' / 'sito.yml'
PUBBLICO = RADICE / 'public'
APPOGGIO = RADICE / '.importa'
LIMITE_MB = 25
IMMAGINI = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
VIDEO = {'.mp4', '.mov', '.m4v', '.webm', '.avi', '.mkv'}


def id_drive(url):
    m = re.search(r'/d/([\w-]+)', url) or re.search(r'[?&]id=([\w-]+)', url)
    return m.group(1) if m else None


def scarica(url, cartella, falliti):
    """Scarica file o cartella. Un file che non scende non blocca gli altri: finisce in `falliti`."""
    cartella.mkdir(parents=True, exist_ok=True)
    if '/folders/' in url:
        elenco = gdown.download_folder(url=url, output=str(cartella), quiet=True, use_cookies=False, skip_download=True)
        for f in elenco:
            dest = Path(f.local_path)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                gdown.download(id=f.id, output=str(dest), quiet=True, use_cookies=False, resume=True)
            except Exception as e:
                falliti.append(f'{f.path}: non scaricato da Drive ({e.__class__.__name__})')
    else:
        gdown.download(id=id_drive(url), output=str(cartella) + '/', quiet=True, use_cookies=False, resume=True)
    return sorted(p for p in cartella.rglob('*') if p.is_file() and not p.name.startswith('.')
                  and not p.name.endswith('.part') and '.web.' not in p.name and not p.name.endswith('-poster.png'))


def comprimi_pdf(sorgente, dest):
    """PDF senza metadati e con immagini ricompresse (150 dpi, JPEG qualità 70)."""
    doc = pymupdf.open(sorgente)
    doc.set_metadata({})                         # toglie autore, software, date
    doc.rewrite_images(dpi_threshold=170, dpi_target=150, quality=70)
    doc.save(dest, garbage=4, deflate=True, clean=True)
    if Path(dest).stat().st_size / 1e6 > LIMITE_MB and len(doc) <= 60:
        # Ripiego per presentazioni corte ma pesantissime: ogni pagina diventa un'immagine JPEG.
        piatto = pymupdf.open()
        for pag in doc:
            pix = pag.get_pixmap(dpi=150)
            nuova = piatto.new_page(width=pag.rect.width, height=pag.rect.height)
            nuova.insert_image(nuova.rect, stream=pix.tobytes('jpeg', jpg_quality=75))
        piatto.save(dest, garbage=4, deflate=True)
        doc = pymupdf.open(dest)
    return doc


def durata(file):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(file)],
                         capture_output=True, text=True).stdout
    return float(json.loads(out or '{}').get('format', {}).get('duration', 0) or 0)


def converti(pid, file, uscita, n, nota):
    """Ritorna (tipo, dati) oppure (None, motivo)."""
    ext = file.suffix.lower()
    base = f'{pid}-{n:02d}'
    if ext in IMMAGINI:
        im = ImageOps.exif_transpose(Image.open(file)).convert('RGB')   # niente EXIF nel file finale
        im.thumbnail((1600, 1600))
        dest = uscita / f'{base}.webp'
        im.save(dest, 'WEBP', quality=80, method=6)
        return 'immagine', dest
    if ext == '.pdf':
        dest = uscita / f'{base}.pdf'
        doc = comprimi_pdf(file, dest)
        mb = dest.stat().st_size / 1e6
        if mb > LIMITE_MB:
            nota.append(f'{dest.name} pesa ancora {mb:.0f} MB dopo la compressione: valuta se dividerlo o toglierlo')
        pag = doc[0].get_pixmap(dpi=110)
        prima = uscita / f'{base}-p1.png'
        pag.save(prima)
        anteprima = uscita / f'{base}-p1.webp'
        Image.open(prima).convert('RGB').save(anteprima, 'WEBP', quality=80, method=6)
        prima.unlink()
        return 'pdf', (dest, anteprima, etichetta(file.stem))
    if ext in VIDEO:
        mp4 = file.with_name(base + '.web.mp4')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(file), '-map_metadata', '-1',
                        '-vf', "scale='min(1280,iw)':-2", '-c:v', 'libx264', '-crf', '26', '-preset', 'slow',
                        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(mp4)], check=True)
        poster = uscita / f'{base}-poster.webp'
        t = max(durata(mp4) * 0.1, 0)
        png = file.with_name(base + '-poster.png')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(mp4), '-frames:v', '1', str(png)], check=True)
        Image.open(png).convert('RGB').save(poster, 'WEBP', quality=80, method=6)
        mb = mp4.stat().st_size / 1e6
        if mb > LIMITE_MB:
            nota.append(f'video troppo grande anche compresso ({mb:.0f} MB): da caricare su YouTube. '
                        f'Copia compressa in {mp4.relative_to(RADICE)}')
            return 'poster', poster
        dest = uscita / f'{base}.mp4'
        shutil.move(mp4, dest)
        return 'video', (dest, poster)
    return None, f'formato non gestito ({ext or "senza estensione"})'


def etichetta(nome):
    """«MappaPianoEditoriale_v2» → «Mappa piano editoriale v2 (PDF)»: da rivedere a mano in sito.yml."""
    parole = re.sub(r'([a-zà-ù])([A-Z0-9])', r'\1 \2', re.sub(r'[_\-]+', ' ', nome)).split()
    frase = ' '.join(parole).strip().replace('"', '')
    return (frase[:1].upper() + frase[1:].lower() if frase else 'Documento') + ' (PDF)'


def rel(p):
    return p.relative_to(PUBBLICO).as_posix()


def blocco(rientro, voci):
    s = ' ' * rientro
    righe = []
    for tipo, dati in voci:
        if tipo == 'galleria':
            righe += [f'{s}- tipo: galleria', f'{s}  immagini:'] + [f'{s}    - {rel(p)}' for p in dati]
        elif tipo == 'pdf':
            righe += [f'{s}- tipo: pdf', f'{s}  file: {rel(dati[0])}', f'{s}  anteprima: {rel(dati[1])}', f'{s}  etichetta: "{dati[2]}"']
        elif tipo == 'video':
            righe += [f'{s}- tipo: video', f'{s}  file: {rel(dati[0])}', f'{s}  poster: {rel(dati[1])}']
    return righe


def importa(pid, progetto, righe):
    report = []
    blocchi = [m for m in progetto.get('media') or [] if m.get('tipo') == 'drive']
    for k, m in enumerate(blocchi, 1):
        url = m['url']
        cartella = APPOGGIO / pid / str(k)
        uscita = PUBBLICO / 'media' / pid
        uscita.mkdir(parents=True, exist_ok=True)
        print(f'[{pid}] scarico {url}', flush=True)
        scartati = []
        try:
            file = scarica(url, cartella, scartati)
        except Exception as e:                    # cartella privata, file cancellato...
            report.append(f'{pid}: NON scaricato ({e.__class__.__name__}: {str(e)[:120]}). Il blocco drive resta: la verifica lo segnalerà.')
            continue
        if not file:
            report.append(f'{pid}: nessun file scaricato. Il blocco drive resta.')
            report += [f'     · {x}' for x in scartati]
            continue
        immagini, voci, note, prima = [], [], [], None
        n = len(list(uscita.glob(f'{pid}-*'))) + 1
        for f in file:
            try:
                tipo, dati = converti(pid, f, uscita, n, note)
            except Exception as e:
                tipo, dati = None, f'errore di conversione: {e}'
            if tipo is None:
                scartati.append(f'{f.relative_to(cartella)}: {dati}')
                continue
            n += 1
            if tipo == 'immagine':
                immagini.append(dati)
                prima = prima or dati
            elif tipo == 'poster':
                prima = prima or dati
            else:
                voci.append((tipo, dati))
                prima = prima or dati[1]
        if immagini:
            voci.insert(0, ('galleria', immagini))
        # riscrivi il blocco drive nel file
        i = next(j for j, r in enumerate(righe) if url in r)
        inizio = i - 1 if re.match(r'\s*- tipo: drive', righe[i - 1]) else i
        rientro = len(righe[inizio]) - len(righe[inizio].lstrip())
        oggi = datetime.date.today().isoformat()
        nuove = [' ' * rientro + f'# importato da Drive il {oggi}: {url}'] + blocco(rientro, voci)
        if not voci:
            nuove.append(' ' * rientro + '# nessun file mostrabile nella pagina: vedi il riepilogo')
        righe[inizio:i + 1] = nuove
        if prima and not progetto.get('immagine'):
            imposta_immagine(righe, pid, rel(prima))
            progetto['immagine'] = rel(prima)
        report.append(f'{pid}: importati {len(immagini)} immagini, '
                      f'{sum(1 for t, _ in voci if t == "pdf")} PDF, {sum(1 for t, _ in voci if t == "video")} video')
        report += [f'   - {x}' for x in note]
        if scartati:
            report.append('   da decidere con Edoardo:')
            report += [f'     · {x}' for x in scartati]
    return report


def imposta_immagine(righe, pid, percorso):
    inizio = next(j for j, r in enumerate(righe) if re.match(rf'\s*- (\{{ )?id: {re.escape(pid)}\b', r))
    for j in range(inizio + 1, len(righe)):
        if re.match(r'\s*- (\{ )?id: ', righe[j]):
            return
        if re.match(r'\s*immagine: ""', righe[j]):
            righe[j] = righe[j].replace('immagine: ""', f'immagine: {percorso}')
            return


def main():
    argomenti = sys.argv[1:]
    if not argomenti:
        sys.exit(__doc__)
    dati = yaml.safe_load(SITO.read_text(encoding='utf-8'))
    progetti = {p['id']: p for p in dati['progetti']}
    con_drive = [pid for pid, p in progetti.items() if any(m.get('tipo') == 'drive' for m in p.get('media') or [])]
    scelti = con_drive if argomenti == ['--tutti'] else argomenti
    for pid in scelti:
        if pid not in progetti:
            sys.exit(f'Progetto «{pid}» non trovato in sito.yml')
    righe = SITO.read_text(encoding='utf-8').split('\n')
    report = []
    for pid in scelti:
        report += importa(pid, progetti[pid], righe)
        SITO.write_text('\n'.join(righe), encoding='utf-8', newline='')   # salva dopo ogni progetto
    print('\n===== RIEPILOGO =====')
    print('\n'.join(report) or 'Nessun blocco drive da importare.')


if __name__ == '__main__':
    main()
