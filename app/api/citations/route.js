import { NextResponse } from "next/server";

function normalizeInputIdentifier(raw) {
  const out = { doi: undefined, arxiv: undefined };
  if (!raw) return out;
  const s = String(raw).trim();
  if (s.toLowerCase().startsWith("http")) {
    const m = s.match(/doi\.org\/(.+)$/i);
    if (m) out.doi = m[1].trim();
    const m2 = s.match(/arxiv\.org\/(?:abs|pdf)\/([0-9]{4}\.[0-9]{5})(?:v\d+)?/i);
    if (m2) out.arxiv = m2[1];
    return out;
  }
  const m3 = s.match(/^(?:arxiv:)?([0-9]{4}\.[0-9]{5})$/i);
  if (m3) {
    out.arxiv = m3[1];
    return out;
  }
  if (s.includes("/")) out.doi = s;
  return out;
}

function s2Headers() {
  const key = process.env.S2_API_KEY || process.env.NEXT_PUBLIC_S2_API_KEY;
  return key ? { "x-api-key": key } : {};
}

async function s2ListCitations(s2Id) {
  const headers = s2Headers();
  const out = [];
  const pageSize = 100;
  for (let offset = 0; offset < 20000; offset += pageSize) {
    const url = `https://api.semanticscholar.org/graph/v1/paper/${s2Id}/citations?fields=year,publicationDate&limit=${pageSize}&offset=${offset}`;
    const r = await fetch(url, { headers, cache: "no-store" });
    if (!r.ok) break;
    const j = await r.json();
    const items = j?.data || [];
    for (const it of items) {
      const cp = it?.citingPaper;
      if (cp) out.push({ year: cp.year || null, date: cp.publicationDate || null });
    }
    if (items.length < pageSize) break;
  }
  return out;
}

function normalizeTitle(t) {
  return String(t || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function authorsSet(aStr) {
  const s = String(aStr || "").toLowerCase();
  if (!s) return new Set();
  return new Set(
    s
      .split(/[,;]|\band\b/i)
      .map((x) => x.trim())
      .filter(Boolean)
  );
}

function authorsOverlap(a, b) {
  if (!a || !b) return true; // if we don't have authors, don't block
  const A = authorsSet(a);
  const B = authorsSet(b);
  if (!A.size || !B.size) return true;
  for (const name of A) if (B.has(name)) return true;
  return false;
}

async function openAlexMeta({ doi, arxiv, title, authors, year }) {
  let url = null;
  if (doi) url = `https://api.openalex.org/works/doi:${doi}`;
  else if (arxiv) url = `https://api.openalex.org/works/arXiv:${arxiv}`;
  if (!url && title) url = `https://api.openalex.org/works?filter=title.search:${encodeURIComponent(title)}&per_page=10`;
  if (!url) return null;
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) return null;
  const j = await r.json();
  if (j?.results) {
    const items = j.results || [];
    const normQ = normalizeTitle(title);
    // Prefer exact title then author/year overlap
    let match = items.find((it) => normalizeTitle(it?.title) === normQ);
    if (!match) {
      match = items.find((it) => {
        const tOk = it?.title && normalizeTitle(it.title).includes(normQ.slice(0, Math.max(8, Math.floor(normQ.length * 0.6))));
        const yOk = !year || String(it?.publication_year || "") === String(year);
        const auths = (it?.authorships || []).map((a) => a?.author?.display_name).filter(Boolean).join(", ");
        const aOk = authorsOverlap(authors, auths);
        return tOk && yOk && aOk;
      });
    }
    return match || null;
  }
  return j;
}

function classifyFromInstitutions(work) {
  const auths = Array.isArray(work?.authorships) ? work.authorships : [];
  const types = new Set();
  for (const a of auths) {
    const insts = Array.isArray(a?.institutions) ? a.institutions : [];
    for (const inst of insts) {
      const t = (inst?.type || "").toString().toLowerCase();
      if (t) types.add(t);
    }
  }
  const hasCompany = types.has("company") || types.has("forprofit") || types.has("business");
  const hasEducation = types.has("education") || types.has("university") || types.has("college");
  if (hasCompany && hasEducation) return "mixed";
  if (hasCompany) return "industry";
  if (hasEducation) return "academia";
  return "unknown";
}

async function openAlexListCitations(citedUrl, { includeAuthorships = false } = {}) {
  const out = [];
  const sectors = { industry: 0, academia: 0, mixed: 0, unknown: 0 };
  const select = includeAuthorships
    ? "&select=authorships,publication_year,publication_date"
    : "&select=publication_year,publication_date";
  for (let page = 1; page <= 25; page++) {
    const r = await fetch(`${citedUrl}${select}&per_page=200&page=${page}`, { cache: "no-store" });
    if (!r.ok) break;
    const j = await r.json();
    const results = j?.results || [];
    for (const w of results) {
      out.push({ year: w?.publication_year || null, date: w?.publication_date || null });
      if (includeAuthorships) {
        const c = classifyFromInstitutions(w);
        if (sectors[c] === undefined) sectors.unknown += 1; else sectors[c] += 1;
      }
    }
    if (results.length < 200) break;
  }
  return { citations: out, sectors };
}

function aggregateByYear(citations) {
  const counts = new Map();
  for (const c of citations || []) {
    const y = c.year || (c.date ? Number(String(c.date).slice(0, 4)) : null);
    if (!y) continue;
    counts.set(y, (counts.get(y) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([year, count]) => ({ year, count }))
    .sort((a, b) => a.year - b.year);
}

function aggregateByMonth(citations) {
  const counts = new Map();
  for (const c of citations || []) {
    const s = c.date ? String(c.date) : null;
    const y = c.year || (s ? Number(s.slice(0, 4)) : null);
    const m = s && s.length >= 7 && (s[4] === '-' || s[4] === '/') ? Number(s.slice(5, 7)) : 1;
    if (!y) continue;
    const key = `${y.toString().padStart(4, '0')}-${m.toString().padStart(2, '0')}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([month, count]) => ({ month, count }))
    .sort((a, b) => (a.month < b.month ? -1 : a.month > b.month ? 1 : 0));
}

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const identifier = searchParams.get("identifier") || undefined;
    let doi = searchParams.get("doi") || undefined;
    let arxiv = searchParams.get("arxivId") || undefined;

    if (identifier && (!doi && !arxiv)) {
      const ids = normalizeInputIdentifier(identifier);
      doi = doi || ids.doi || undefined;
      arxiv = arxiv || ids.arxiv || undefined;
    }

    let s2Id = doi ? `DOI:${doi}` : arxiv ? `arXiv:${arxiv}` : undefined;
    let usedSource = null;
    let usedDoi = doi || null;
  let citations = [];
  let sectorCounts = { industry: 0, academia: 0, mixed: 0, unknown: 0 };

    // Try Semantic Scholar first
    if (s2Id) {
      citations = await s2ListCitations(s2Id);
      if (citations.length) usedSource = "s2";
    }

    // Fallback to OpenAlex if needed
    let meta = null;
    if (!citations.length) {
      meta = await openAlexMeta({
        doi,
        arxiv,
        title: searchParams.get("title") || undefined,
        authors: searchParams.get("authors") || undefined,
        year: searchParams.get("year") || undefined,
      });
      const citedUrl = meta?.cited_by_api_url;
      if (meta?.doi && !usedDoi) usedDoi = String(meta.doi).replace(/^https?:\/\/doi\.org\//i, "");
      if (citedUrl) {
        const { citations: olCitations, sectors } = await openAlexListCitations(citedUrl, { includeAuthorships: true });
        citations = olCitations;
        sectorCounts = sectors;
        if (citations.length) usedSource = "openalex";
      }
    }

    // If we used S2 for citations, still try to compute sector counts via OpenAlex citing works
    if (usedSource === "s2") {
      if (!meta) {
        meta = await openAlexMeta({
          doi: usedDoi || doi,
          arxiv,
          title: searchParams.get("title") || undefined,
          authors: searchParams.get("authors") || undefined,
          year: searchParams.get("year") || undefined,
        });
      }
      const citedUrl2 = meta?.cited_by_api_url;
      if (citedUrl2) {
        const { sectors } = await openAlexListCitations(citedUrl2, { includeAuthorships: true });
        sectorCounts = sectors;
      }
    }

    const series = aggregateByYear(citations);
    const seriesMonthly = aggregateByMonth(citations);
  return NextResponse.json({ series, seriesMonthly, total: citations.length, doi: usedDoi, source: usedSource, sectorCounts });
  } catch (e) {
  return NextResponse.json({ series: [], seriesMonthly: [], total: 0, sectorCounts: { industry: 0, academia: 0, mixed: 0, unknown: 0 }, error: String(e) }, { status: 500 });
  }
}
