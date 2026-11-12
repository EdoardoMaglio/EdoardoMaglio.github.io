"""Scarica una volta la copertina dei video YouTube che in sito.yml hanno `poster: ""`.

Uso:  python strumenti/poster_youtube.py

La copertina viene salvata in public/img/<id-progetto>-poster.webp e scritta in sito.yml.
Così il visitatore non contatta YouTube finché non preme Riproduci.
"""
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from PIL import Image

RADICE = Path(__file__).resolve().parent.parent
SITO = RADICE / 'contenuti' / 'sito.yml'
UA = {'User-Agent': 'Mozilla/5.0 (poster_youtube)'}


def scarica(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def miniatura(m):
    if m.get('playlist'):
        q = urllib.parse.quote(f'https://www.youtube.com/playlist?list={m["playlist"]}', safe='')
        info = json.loads(scarica(f'https://www.youtube.com/oembed?format=json&url={q}'))
        url = info['thumbnail_url'].replace('hqdefault', 'maxresdefault')
        try:
            return scarica(url)
        except Exception:
            return scarica(info['thumbnail_url'])
    for nome in ('maxresdefault', 'sddefault', 'hqdefault'):
        try:
            dati = scarica(f'https://i.ytimg.com/vi/{m["id"]}/{nome}.jpg')
            if Image.open(io.BytesIO(dati)).width > 120:      # YouTube risponde con un segnaposto 120 px
                return dati
        except Exception:
            pass
    raise RuntimeError('nessuna miniatura trovata')


def main():
    dati = yaml.safe_load(SITO.read_text(encoding='utf-8'))
    righe = SITO.read_text(encoding='utf-8').split('\n')
    for p in dati['progetti']:
        for m in p.get('media') or []:
            if m.get('tipo') != 'youtube' or m.get('poster') or m.get('miniatura') is False:
                continue
            chiave = m.get('id') or m.get('playlist')
            dest = RADICE / 'public' / 'img' / f'{p["id"]}-poster.webp'
            im = Image.open(io.BytesIO(miniatura(m))).convert('RGB')
            # le miniature 4:3 di YouTube hanno bande nere: ritaglio in 16:9
            w, h = im.size
            if abs(w / h - 4 / 3) < 0.05:
                nh = round(w * 9 / 16)
                im = im.crop((0, (h - nh) // 2, w, (h + nh) // 2))
            im.save(dest, 'WEBP', quality=82, method=6)
            i = next(j for j, r in enumerate(righe) if re.search(rf'(id|playlist): "?{re.escape(str(chiave))}"?\s*$', r))
            for j in range(i + 1, min(i + 4, len(righe))):
                if 'poster: ""' in righe[j]:
                    righe[j] = righe[j].replace('poster: ""', f'poster: img/{dest.name}')
                    break
            print(f'{p["id"]}: {dest.relative_to(RADICE)} ({im.width}x{im.height})')
    SITO.write_text('\n'.join(righe), encoding='utf-8', newline='')


if __name__ == '__main__':
    main()
