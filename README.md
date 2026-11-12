# sito-portfolio

Sito portfolio di Edoardo Maglio, costruito con [Astro](https://astro.build) e pubblicato su GitHub Pages: <https://edoardomaglio.github.io>.

## Come modificare il sito

1. Tutti i testi, le date, i ruoli e i link sono in **`contenuti/sito.yml`**. Non serve toccare altro.
2. Dal telefono: apri il file su github.com, premi la matita, cambia la riga, premi **Commit changes**. Il sito si aggiorna da solo in un paio di minuti.
3. Rientro di 2 spazi, mai Tab. Un testo con i due punti `:` va tra virgolette. Un campo vuoto `""` non compare sul sito.
4. Date sempre come `2025-07`. L'ordine nel file è l'ordine sul sito: per spostare un progetto, sposta il suo blocco.
5. `visibile: false` nasconde un progetto, un premio o un racconto senza cancellarlo.
6. Immagini e PDF vanno in `public/` e si scrivono senza `public/`: `immagine: img/foto.jpg`.
7. Materiale su Google Drive: scrivi `- tipo: drive` e `url:` nel blocco `media`, poi lancia `python strumenti/importa_drive.py <id-progetto>`.

**Sul computer, con VS Code:** installa l'estensione **YAML** di Red Hat (`redhat.vscode-yaml`). Legge `contenuti/sito.schema.json` e sottolinea gli errori mentre scrivi: una categoria che non esiste, una data scritta male, un campo con un refuso. Con Ctrl+Spazio propone i valori ammessi.

## Quando pubblichi

- A ogni modifica su `main`, GitHub **prima controlla** `sito.yml` e **solo se è tutto a posto** pubblica.
- Se c'è un errore, la pubblicazione non parte e **online resta la versione precedente**: il sito non si rompe mai.
- Per leggere l'errore: su github.com apri la scheda **Actions**, clicca l'esecuzione con la **X rossa**, poi **Verifica e costruzione**. Il messaggio dice il numero di riga e cosa correggere.
- In fondo alla verifica c'è anche l'elenco «Campi mancanti»: non blocca nulla, ti ricorda cosa manca.

## Video: su YouTube, non nel repository

I video più pesanti di qualche MB vanno su YouTube come **«Non in elenco»**, e nel sito si mette solo il codice (vedi l'esempio sotto). Non caricarli nel repository: ogni file caricato o sostituito resta per sempre nella cronologia, e il repository diventa sempre più lento da scaricare e da pubblicare. La verifica avvisa sopra i 25 MB.

## Esempi da copiare

Incolla il blocco nella sezione giusta di `sito.yml` e cambia i valori. Le righe con `#` sono note.

**Aggiungere un progetto** (nella sezione `progetti:`, dove vuoi che compaia):

```yaml
  - id: nome-breve-del-progetto      # minuscole e trattini: diventa /lavori/nome-breve-del-progetto/
    titolo: Nome del progetto
    categoria: video                 # video | giochi | digitale
    sezione: lavori                  # lavori | scartati | archivio
    in_evidenza: false
    anno: 2026
    ruolo: Sceneggiatura, regia, montaggio
    strumenti: [DaVinci Resolve, Blender]
    stato: concluso                  # online | in_uso | concluso | in_sviluppo | in_testing | prototipo | concept | fermo
    testo: "Una o due frasi su cos'è il progetto."
    immagine: img/nome-del-progetto.jpg   # vuoto "" = copertina tipografica
    alt: "Cosa si vede nell'immagine"
    link:
      - { etichetta: Guarda il corto su YouTube, url: "https://www.youtube.com/watch?v=CODICE" }
```

**Aggiungere un premio** (nella sezione `premi:`):

```yaml
  - premio: Nome del premio
    edizione: II edizione, sezione giovani
    risultato: 1° posto
    opera: Titolo del racconto
    anno: 2026
    url: "https://pagina-con-l-esito"
```

**Spostare un progetto in «Giochi scartati»:** nel blocco del progetto cambia una riga.

```yaml
    sezione: scartati                # era: lavori
```

**Scegliere le «In evidenza»** (da 0 a 4, solo progetti online, in uso, conclusi o prototipi giocabili): nel blocco di ciascun progetto scelto, e false negli altri.

```yaml
    in_evidenza: true
```

**Aggiungere un video YouTube** a un progetto (il codice è quello dopo `v=` nell'indirizzo):

```yaml
    media:
      - tipo: youtube
        id: "2kq0ovLG3LI"
        poster: ""                   # poi lancia: python strumenti/poster_youtube.py
```

**Nascondere un progetto** senza cancellarlo: aggiungi una riga nel suo blocco. Vale anche per premi e racconti.

```yaml
    visibile: false
```

## Per chi sviluppa

```sh
npm install       # una volta sola
npm run dev       # anteprima locale su http://localhost:4321
npm run verifica  # controlla contenuti/sito.yml ed elenca i campi mancanti
npm run build     # verifica + build in dist/
python strumenti/poster_youtube.py   # copertine locali per i video YouTube nuovi
python strumenti/importa_drive.py <id-progetto>   # materiale da Google Drive dentro il sito
```

Se aggiungi una categoria o uno stato in `sito.yml`, aggiungilo anche negli elenchi di `contenuti/sito.schema.json`.
