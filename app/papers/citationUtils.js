export async function resolveDoiOrFindByTitle({ doi, title, arxivId }) {
  // If DOI provided, return it
  if (doi) return { doi };
  if (!title && !arxivId) return {};

  // Prefer server route (more robust + normalized matching across providers)
  try {
    const params = new URLSearchParams({ ...(title ? { title } : {}), ...(arxivId ? { arxivId } : {}) });
    const r = await fetch(`/api/resolve-doi?${params.toString()}`, { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      if (j?.doi) return { doi: j.doi, via: j.via || "api" };
    }
  } catch {}

  // Try Crossref first
  try {
    const r = await fetch(
      `https://api.crossref.org/works?rows=1&query.title=${encodeURIComponent(title)}`,
      { cache: "no-store" }
    );
    if (r.ok) {
      const j = await r.json();
      const item = j?.message?.items?.[0];
      const found = item?.DOI;
      if (found) return { doi: found };
    }
  } catch {}

  // Fallback to OpenAlex
  try {
    const r = await fetch(
      `https://api.openalex.org/works?search=${encodeURIComponent(title)}&per_page=1`,
      { cache: "no-store" }
    );
    if (r.ok) {
      const j = await r.json();
      const item = j?.results?.[0];
      const found = item?.doi;
      if (found) return { doi: found.replace(/^https?:\/\/doi\.org\//i, "") };
    }
  } catch {}

  return {};
}

function normalizeTitle(t) {
  return String(t || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function searchSemanticScholarByTitle(title, s2ApiKey) {
  try {
    const headers = s2ApiKey ? { "x-api-key": s2ApiKey } : {};
    const url = `https://api.semanticscholar.org/graph/v1/paper/search?query=${encodeURIComponent(title)}&limit=5&fields=paperId,title,year,externalIds`;
    const r = await fetch(url, { headers, cache: "no-store" });
    if (!r.ok) return null;
    const j = await r.json();
    const items = j?.data || [];
    if (!items.length) return null;
    const normQ = normalizeTitle(title);
    let best = items.find((it) => normalizeTitle(it.title) === normQ) || items[0];
    const ext = (best && best.externalIds) || {};
    return { s2Id: best.paperId, doi: ext.DOI || null };
  } catch {
    return null;
  }
}

async function getOpenAlexWorkByTitle(title) {
  try {
    const r = await fetch(`https://api.openalex.org/works?filter=title.search:${encodeURIComponent(title)}&per_page=5`, { cache: "no-store" });
    if (!r.ok) return null;
    const j = await r.json();
    const items = j?.results || [];
    if (!items.length) return null;
    const normQ = normalizeTitle(title);
    const best = items.find((it) => normalizeTitle(it.title) === normQ) || items[0];
    const doi = best?.doi ? best.doi.replace(/^https?:\/\/doi\.org\//i, "") : null;
    return { id: best?.id, doi, citedByUrl: best?.cited_by_api_url };
  } catch {
    return null;
  }
}

export async function fetchCitationsWithDates({ doi, arxivId, title, s2ApiKey }) {
  // Prefer Semantic Scholar
  const headers = s2ApiKey ? { "x-api-key": s2ApiKey } : {};
  let s2Id = doi ? `DOI:${doi}` : arxivId ? `arXiv:${arxivId}` : null;
  // If we don't have an id yet but have a title, try S2 search
  if (!s2Id && title) {
    const found = await searchSemanticScholarByTitle(title, s2ApiKey);
    if (found?.s2Id) s2Id = found.s2Id; // this is an internal S2 paper id (not DOI: prefix)
    if (!doi && found?.doi) doi = found.doi;
  }
  if (s2Id) {
    try {
      const out = [];
      const pageSize = 100;
      for (let offset = 0; offset < 10000; offset += pageSize) {
        const url = `https://api.semanticscholar.org/graph/v1/paper/${s2Id}/citations?fields=year,publicationDate&limit=${pageSize}&offset=${offset}`;
        const r = await fetch(url, { headers, cache: "no-store" });
        if (!r.ok) break;
        const j = await r.json();
        const items = j?.data || [];
        out.push(
          ...items
            .map((it) => it?.citingPaper)
            .filter(Boolean)
            .map((cp) => ({ year: cp.year || null, date: cp.publicationDate || null }))
        );
        if (items.length < pageSize) break;
      }
      if (out.length) return out;
    } catch {}
  }

  // Fallback OpenAlex by DOI
  if (doi) {
    try {
      const metaRes = await fetch(`https://api.openalex.org/works/doi:${doi}`, { cache: "no-store" });
      if (metaRes.ok) {
        const meta = await metaRes.json();
        const citeUrl = meta?.cited_by_api_url;
        const out = [];
        let page = 1;
        while (page <= 20 && citeUrl) { // up to ~4000 citing works
          const r = await fetch(`${citeUrl}&per_page=200&page=${page}`, { cache: "no-store" });
          if (!r.ok) break;
          const j = await r.json();
          const results = j?.results || [];
          out.push(
            ...results.map((w) => ({
              year: w.publication_year || null,
              date: w.publication_date || null,
            }))
          );
          if (results.length < 200) break;
          page += 1;
        }
        return out;
      }
    } catch {}
  }

  // Last resort: OpenAlex by title
  if (title) {
    try {
      const work = await getOpenAlexWorkByTitle(title);
      if (work?.citedByUrl) {
        const out = [];
        let page = 1;
        while (page <= 20) {
          const r = await fetch(`${work.citedByUrl}&per_page=200&page=${page}`, { cache: "no-store" });
          if (!r.ok) break;
          const j = await r.json();
          const results = j?.results || [];
          out.push(
            ...results.map((w) => ({
              year: w.publication_year || null,
              date: w.publication_date || null,
            }))
          );
          if (results.length < 200) break;
          page += 1;
        }
        return out;
      }
    } catch {}
  }
  return [];
}

export function aggregateByYear(citations) {
  const counts = new Map();
  for (const c of citations) {
    const y = c.year || (c.date ? Number(String(c.date).slice(0, 4)) : null);
    if (!y) continue;
    counts.set(y, (counts.get(y) || 0) + 1);
  }
  const series = Array.from(counts.entries())
    .map(([year, count]) => ({ year, count }))
    .sort((a, b) => a.year - b.year);
  return series;
}

export function computeYoY(series) {
  const out = [];
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].count;
    const cur = series[i].count;
    if (prev === 0) continue;
    out.push({ year: series[i].year, growth: ((cur - prev) / prev) * 100 });
  }
  return out;
}
