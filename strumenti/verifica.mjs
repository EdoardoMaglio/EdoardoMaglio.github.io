// Controlla contenuti/sito.yml prima di costruire il sito.
//   npm run verifica
// Errori  → la costruzione si ferma, con il numero di riga.
// Campi mancanti → solo un elenco: il sito li nasconde.
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { parseDocument, LineCounter, visit, isScalar } from 'yaml';

const RADICE = process.cwd();
const FILE = join(RADICE, 'contenuti', 'sito.yml');
const PUBBLICO = join(RADICE, 'public');
const LIMITE_MB = 25;
const SEZIONI = ['lavori', 'scartati', 'archivio'];
const MEDIA = ['youtube', 'video', 'pdf', 'galleria', 'drive'];
const STATI_EVIDENZA = ['online', 'in_uso', 'concluso', 'prototipo'];   // prototipo: deciso da Edoardo il 12/11/2026
const MAX_EVIDENZA = 4;

const lc = new LineCounter();
const doc = parseDocument(readFileSync(FILE, 'utf-8'), { lineCounter: lc });
const errori = [];
const avvisi = [];
const mancanti = [];

if (doc.errors.length) {
  for (const e of doc.errors) errori.push(`riga ${e.linePos?.[0]?.line ?? '?'}: il file non si legge (${e.code}). Controlla rientri, due punti e virgolette.`);
  fine();
}

const riga = (percorso) => {
  for (let p = percorso; p.length; p = p.slice(0, -1)) {
    const n = doc.getIn(p, true);
    if (n?.range) return lc.linePos(n.range[0]).line;
  }
  return '?';
};
const vuoto = (v) => v === null || v === undefined || (Array.isArray(v) ? v.length === 0 : String(v).trim() === '');
const d = doc.toJS();

// 1. Testi che non devono mai arrivare sul sito, e link a Google Drive
visit(doc, {
  Scalar(_, n) {
    if (typeof n.value !== 'string' || !n.range) return;
    const r = lc.linePos(n.range[0]).line;
    if (/\[MANCA|\bTODO\b|\[da confermare/i.test(n.value)) errori.push(`riga ${r}: «${n.value.slice(0, 50)}» è un segnaposto. Lascia il campo vuoto ("") e il sito lo nasconderà.`);
    if (/(drive|docs)\.google\.com/.test(n.value)) errori.push(`riga ${r}: link a Google Drive. Sul sito il materiale si mostra dentro la pagina: lancia  python strumenti/importa_drive.py <id-progetto>`);
  },
});

// 2. File indicati: devono esistere in public/ e non contenere dati personali nel nome
function file(f, percorso, video = false) {
  if (vuoto(f)) return;
  const pieno = join(PUBBLICO, String(f));
  if (/(^|[^a-z])s\d{6}([^0-9]|$)|matricol/i.test(String(f))) errori.push(`riga ${riga(percorso)}: il nome del file «${f}» sembra contenere un numero di matricola. Rinominalo.`);
  if (!existsSync(pieno)) return errori.push(`riga ${riga(percorso)}: il file «${f}» non esiste in public/.`);
  if (video) {
    const mb = statSync(pieno).size / 1e6;
    if (mb > LIMITE_MB) avvisi.push(`riga ${riga(percorso)}: il video «${f}» pesa ${mb.toFixed(0)} MB (limite ${LIMITE_MB}). Meglio caricarlo su YouTube.`);
  }
}

// 3. Profilo
if (vuoto(d.profilo?.nome)) errori.push(`riga ${riga(['profilo'])}: manca profilo → nome.`);
if (vuoto(d.profilo?.cv_pdf)) mancanti.push(`riga ${riga(['profilo', 'cv_pdf'])} · profilo: cv_pdf (il pulsante «Scarica il CV» non compare)`);
else file(d.profilo.cv_pdf, ['profilo', 'cv_pdf']);
(d.profilo?.link ?? []).forEach((l, i) => vuoto(l.url) && mancanti.push(`riga ${riga(['profilo', 'link', i])} · profilo: link ${l.nome}`));

// 4. Progetti
const categorie = (d.categorie ?? []).map((c) => c.id);
const stati = Object.keys(d.stati ?? {});
const visti = new Map();
let evidenza = 0;
(d.progetti ?? []).forEach((p, i) => {
  const P = ['progetti', i];
  const nome = p.id || p.titolo || `n. ${i + 1}`;
  for (const k of ['id', 'titolo', 'categoria', 'sezione']) if (vuoto(p[k])) errori.push(`riga ${riga(P)}: al progetto «${nome}» manca il campo obbligatorio «${k}».`);
  booleano(p.visibile, [...P, 'visibile'], 'visibile');
  booleano(p.in_evidenza, [...P, 'in_evidenza'], 'in_evidenza');
  data(p.da, [...P, 'da']); data(p.a, [...P, 'a']);
  const mostrato = p.visibile !== false;
  if (p.id && !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(p.id)) errori.push(`riga ${riga([...P, 'id'])}: l'id «${p.id}» può contenere solo lettere minuscole, numeri e trattini.`);
  if (p.id && visti.has(p.id)) errori.push(`riga ${riga([...P, 'id'])}: l'id «${p.id}» è già usato alla riga ${visti.get(p.id)}.`);
  if (p.id) visti.set(p.id, riga([...P, 'id']));
  if (p.id && categorie.includes(p.id)) errori.push(`riga ${riga([...P, 'id'])}: l'id «${p.id}» è uguale a una categoria: i due indirizzi si scontrerebbero.`);
  if (p.categoria && !categorie.includes(p.categoria)) errori.push(`riga ${riga([...P, 'categoria'])}: categoria «${p.categoria}» non prevista. Usa: ${categorie.join(' | ')}.`);
  if (p.sezione && !SEZIONI.includes(p.sezione)) errori.push(`riga ${riga([...P, 'sezione'])}: sezione «${p.sezione}» non prevista. Usa: ${SEZIONI.join(' | ')}.`);
  if (p.stato && !stati.includes(p.stato)) errori.push(`riga ${riga([...P, 'stato'])}: stato «${p.stato}» non previsto. Usa: ${stati.join(' | ')}.`);
  if (p.in_evidenza === true && mostrato) {
    evidenza++;
    if (p.sezione !== 'lavori') errori.push(`riga ${riga([...P, 'in_evidenza'])}: «${nome}» è in evidenza ma sta in «${p.sezione}».`);
    if (!STATI_EVIDENZA.includes(p.stato)) errori.push(`riga ${riga([...P, 'in_evidenza'])}: «${nome}» è in evidenza ma è «${p.stato}». In evidenza vanno solo progetti ${STATI_EVIDENZA.join(', ')}.`);
  }
  if (mostrato) file(p.immagine, [...P, 'immagine']);   // un progetto nascosto può avere file già tolti da public/
  if (p.sezione === 'lavori' && mostrato) {
    if (vuoto(p.anno) && vuoto(p.da)) mancanti.push(`riga ${riga(P)} · ${nome}: anno (o da / a)`);
    for (const k of ['ruolo', 'stato', 'testo']) if (vuoto(p[k])) mancanti.push(`riga ${riga(P)} · ${nome}: ${k}`);
    if (!vuoto(p.immagine) && vuoto(p.alt)) mancanti.push(`riga ${riga([...P, 'immagine'])} · ${nome}: alt (descrizione dell'immagine per chi non vede)`);
  }
  (mostrato ? p.media ?? [] : []).forEach((m, j) => {
    const M = [...P, 'media', j];
    if (!MEDIA.includes(m.tipo)) return errori.push(`riga ${riga(M)}: tipo di media «${m.tipo}» non previsto. Usa: ${MEDIA.join(' | ')}.`);
    if (m.tipo === 'youtube' && vuoto(m.id) && vuoto(m.playlist)) errori.push(`riga ${riga(M)}: al video YouTube di «${nome}» manca id (o playlist).`);
    if (m.tipo === 'youtube' && vuoto(m.poster) && mostrato) mancanti.push(`riga ${riga(M)} · ${nome}: poster del video YouTube (lancia  python strumenti/poster_youtube.py)`);
    if (m.tipo === 'video') { if (vuoto(m.file)) errori.push(`riga ${riga(M)}: al video di «${nome}» manca file.`); file(m.file, [...M, 'file'], true); file(m.poster, [...M, 'poster']); }
    if (m.tipo === 'youtube') file(m.poster, [...M, 'poster']);
    if (m.tipo === 'pdf') { if (vuoto(m.file)) errori.push(`riga ${riga(M)}: al PDF di «${nome}» manca file.`); file(m.file, [...M, 'file']); file(m.anteprima, [...M, 'anteprima']); }
    if (m.tipo === 'galleria') (m.immagini ?? []).forEach((f, k) => file(f, [...M, 'immagini', k]));
  });
  (p.link ?? []).forEach((l, j) => {
    if (vuoto(l.url)) { if (mostrato) mancanti.push(`riga ${riga([...P, 'link', j])} · ${nome}: url del link «${l.etichetta}»`); }
    else if (!/^https:\/\//.test(l.url)) errori.push(`riga ${riga([...P, 'link', j])}: il link «${l.url}» deve cominciare con https://`);
    if (!vuoto(l.url) && vuoto(l.etichetta)) errori.push(`riga ${riga([...P, 'link', j])}: al link «${l.url}» manca l'etichetta del pulsante.`);
  });
  (p.clienti ?? []).forEach((c, j) => {
    if (typeof c === 'string' || !mostrato) return;     // elenco di soli nomi: niente altro da controllare
    for (const k of ['periodo', 'ruolo']) if (vuoto(c[k])) mancanti.push(`riga ${riga([...P, 'clienti', j])} · ${nome} → ${c.nome}: ${k}`);
  });
});
if (evidenza > MAX_EVIDENZA) errori.push(`riga ${riga(['progetti'])}: ci sono ${evidenza} progetti con in_evidenza: true. Il massimo è ${MAX_EVIDENZA}.`);

// 5. Premi e pubblicazioni
(d.premi ?? []).forEach((x, i) => {
  booleano(x.visibile, ['premi', i, 'visibile'], 'visibile');
  if (vuoto(x.premio)) errori.push(`riga ${riga(['premi', i])}: al premio manca il nome («premio»).`);
  if (x.visibile === false) return;
  for (const k of ['anno', 'risultato', 'opera', 'url']) if (vuoto(x[k])) mancanti.push(`riga ${riga(['premi', i])} · premio ${x.premio}: ${k}`);
});
(d.pubblicazioni ?? []).forEach((x, i) => {
  booleano(x.visibile, ['pubblicazioni', i, 'visibile'], 'visibile');
  if (vuoto(x.titolo) && vuoto(x.testo)) errori.push(`riga ${riga(['pubblicazioni', i])}: la pubblicazione ha bisogno di «titolo» oppure di «testo».`);
  if (!vuoto(x.testo) || x.visibile === false) return;     // riga libera: niente altro da controllare
  for (const k of ['anno', 'url']) if (vuoto(x[k])) mancanti.push(`riga ${riga(['pubblicazioni', i])} · ${x.titolo}: ${k}`);
});

(d.racconti ?? []).forEach((x, i) => {
  booleano(x.visibile, ['racconti', i, 'visibile'], 'visibile');
  if (vuoto(x.titolo)) errori.push(`riga ${riga(['racconti', i])}: al racconto manca il titolo.`);
});

// 6. Date in un solo formato
for (const sez of ['esperienze', 'formazione']) (d[sez] ?? []).forEach((x, i) => {
  for (const k of ['da', 'a']) {
    data(x[k], [sez, i, k]);
  }
});

fine();

function data(v, percorso) {
  const s = String(v ?? '');
  if (s && !/^\d{4}(-\d{2})?$|^oggi$/.test(s)) errori.push(`riga ${riga(percorso)}: la data «${s}» va scritta come 2025-07 (anno-mese), oppure «oggi».`);
}
function booleano(v, percorso, campo) {
  if (v !== undefined && v !== null && typeof v !== 'boolean') errori.push(`riga ${riga(percorso)}: «${campo}» può essere solo true o false (senza virgolette).`);
}

function fine() {
  if (mancanti.length) {
    console.log(`\nCampi mancanti (${mancanti.length}): non bloccano, sul sito non compaiono.`);
    for (const m of mancanti) console.log('  · ' + m);
  }
  if (avvisi.length) {
    console.log('\nAvvisi:');
    for (const a of avvisi) console.log('  ! ' + a);
  }
  if (errori.length) {
    console.error(`\nERRORI in contenuti/sito.yml (${errori.length}): il sito non viene costruito finché non li correggi.`);
    for (const e of errori) console.error('  ✗ ' + e);
    process.exit(1);
  }
  console.log('\nsito.yml: nessun errore.');
}
