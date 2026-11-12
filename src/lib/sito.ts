// Legge contenuti/sito.yml: è l'unica fonte dei testi del sito.
// I controlli (campi obbligatori, file mancanti, link Drive...) sono in strumenti/verifica.mjs.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';

export type Link = { etichetta: string; url: string };
export type Media =
  | { tipo: 'youtube'; id?: string; playlist?: string; poster?: string }
  | { tipo: 'video'; file: string; poster?: string }
  | { tipo: 'pdf'; file: string; anteprima?: string; etichetta?: string }
  | { tipo: 'galleria'; immagini: string[]; didascalie?: string[] };
export type Cliente = string | { nome: string; periodo?: string; ruolo?: string; url?: string; link?: Link[] };
export type Progetto = {
  id: string; titolo: string; categoria: string; sezione: 'lavori' | 'scartati' | 'archivio';
  visibile?: boolean; in_evidenza?: boolean; anno?: string | number; da?: string; a?: string; ruolo?: string; strumenti?: string[]; stato?: string;
  riconoscimenti?: string[]; testo?: string; immagine?: string; alt?: string; media?: Media[]; link?: Link[]; clienti?: Cliente[];
};
export type Categoria = { id: string; nome: string; lettera: string; descrizione: string };

// Percorso dalla radice del progetto: Astro e npm partono sempre da lì.
const sorgente = readFileSync(join(process.cwd(), 'contenuti', 'sito.yml'), 'utf-8');
export const sito = parse(sorgente) as any;

/** Vero se l'elemento va mostrato: `visibile: false` lo nasconde senza cancellarlo. */
export const visibile = (x: any) => x && x.visibile !== false;
const soloVisibili = (l: any[] | undefined) => (l ?? []).filter(visibile);
export const premi = soloVisibili(sito.premi);
export const pubblicazioni = soloVisibili(sito.pubblicazioni);
export const sceneggiature = soloVisibili(sito.sceneggiature);
export const racconti = soloVisibili(sito.racconti);
export const t: Record<string, any> = sito.testi;

/** Vero se il campo ha un contenuto da mostrare. */
export const pieno = (v: unknown): boolean =>
  v !== null && v !== undefined && (Array.isArray(v) ? v.length > 0 : String(v).trim() !== '');

/** Sostituisce {n}, {titolo}, {anno} nei testi dell'interfaccia. */
export const testo = (chiave: string, valori: Record<string, string | number> = {}): string =>
  String(t[chiave] ?? '').replace(/\{(\w+)\}/g, (_, k) => String(valori[k] ?? ''));

/** 2025-07 → «lug 2025»; 2021 → «2021»; oggi → «oggi». */
export function data(v: unknown): string {
  const s = String(v ?? '').trim();
  if (s === 'oggi') return t.oggi;
  const m = s.match(/^(\d{4})-(\d{2})$/);
  return m ? `${t.mesi[Number(m[2]) - 1]} ${m[1]}` : s;
}
export const periodo = (da: unknown, a: unknown) => [data(da), data(a)].filter(pieno).join(' – ');

/** «2024-2025» → «2024–2025» (lineetta tipografica tra due anni). */
export const anno = (v: unknown) => String(v ?? '').replace(/(\d{4})-(\d{4})/, '$1–$2');

/** Quando mostrare per un progetto: il periodo da/a se c'è, altrimenti l'anno. */
export const quando = (p: { anno?: unknown; da?: unknown; a?: unknown }) =>
  pieno(p.da) ? periodo(p.da, p.a) : anno(p.anno);

export const categorie: Categoria[] = sito.categorie;
export const categoria = (id: string) => categorie.find((c) => c.id === id)!;
export const stato = (id?: string) => (id ? sito.stati[id] : undefined) as { nome: string; vivo?: boolean } | undefined;

export const progetti: Progetto[] = soloVisibili(sito.progetti);
export const lavori = progetti.filter((p) => p.sezione === 'lavori');
export const scartati = progetti.filter((p) => p.sezione === 'scartati');
export const archivio = progetti.filter((p) => p.sezione === 'archivio');
export const inEvidenza = lavori.filter((p) => p.in_evidenza);
export const perCategoria = (id: string) => lavori.filter((p) => p.categoria === id);

/** Percorso pubblico di un file in public/ ("img/x.jpg" → "/img/x.jpg"). */
export const src = (f?: string) => (f ? '/' + f.replace(/^\/+/, '') : '');

/** Immagine per la scheda: la propria, altrimenti la prima del materiale. */
export function copertina(p: Progetto): string {
  if (pieno(p.immagine)) return p.immagine!;
  for (const m of p.media ?? []) {
    if ((m.tipo === 'youtube' || m.tipo === 'video') && pieno(m.poster)) return m.poster!;
    if (m.tipo === 'pdf' && pieno(m.anteprima)) return m.anteprima!;
    if (m.tipo === 'galleria' && m.immagini?.length) return m.immagini[0];
  }
  return '';
}

export const linkPieni = (l?: Link[]) => (l ?? []).filter((x) => pieno(x.url) && pieno(x.etichetta));
export const voci = (l?: string[]) => (l ?? []).filter(pieno);
