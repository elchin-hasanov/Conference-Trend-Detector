import { NextResponse } from "next/server";

function normalizeTitle(t) {
  return String(t || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function authorsOverlap(a, b) {
  const makeSet = (s) =>
    new Set(
      String(s || "")
        .toLowerCase()
        .split(/[,;]|\band\b/i)
        .map((x) => x.trim())
        .filter(Boolean)
    );
  const A = makeSet(a);
  const B = makeSet(b);
  if (!A.size || !B.size) return true;
  for (const x of A) if (B.has(x)) return true;
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

function classifyCitingWork(work) {
  const auths = Array.isArray(work?.authorships) ? work.authorships : [];
  let hasEducation = false;
  let hasCompany = false;
  let hasGovernment = false;
  for (const a of auths) {
    const insts = Array.isArray(a?.institutions) ? a.institutions : [];
    for (const inst of insts) {
  const t = (inst?.type || "").toString().toLowerCase();
  // Map common OpenAlex institution types
  if (t === "education" || t === "university" || t === "college" || t === "facility" || t === "archive") hasEducation = true;
  else if (t === "company" || t === "forprofit" || t === "business") hasCompany = true;
  else if (t === "government") hasGovernment = true;
    }
  }
  const types = [hasEducation, hasCompany, hasGovernment].filter(Boolean).length;
  if (types === 0) return "unknown";
  if (types > 1) return "mixed";
  if (hasGovernment) return "government";
  if (hasCompany) return "industry";
  return "academia";
}

function addQuery(url, query) {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}${query}`;
}

async function listCitingWithInstitutions(citedUrl) {
  const counts = { academia: 0, industry: 0, government: 0, mixed: 0, unknown: 0 };
  const total = { value: 0 };
  let cursor = "*";
  for (let page = 1; page <= 50; page++) {
    const mailto = process.env.NEXT_PUBLIC_OPENALEX_MAILTO ? `&mailto=${encodeURIComponent(process.env.NEXT_PUBLIC_OPENALEX_MAILTO)}` : "";
    const url = addQuery(citedUrl, `per_page=200&cursor=${encodeURIComponent(cursor)}${mailto}`);
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) break;
    const j = await r.json();
    const results = j?.results || [];
    for (const w of results) {
      const cls = classifyCitingWork(w);
      counts[cls] = (counts[cls] || 0) + 1;
      total.value += 1;
    }
    const next = j?.meta?.next_cursor;
    if (!next || results.length === 0) break;
    cursor = next;
  }
  return { counts, total: total.value };
}

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const doi = searchParams.get("doi") || undefined;
    const title = searchParams.get("title") || undefined;
    const authors = searchParams.get("authors") || undefined;
    const year = searchParams.get("year") || undefined;
    const arxiv = searchParams.get("arxivId") || undefined;

  const meta = await openAlexMeta({ doi, arxiv, title, authors, year });
  let citedUrl = meta?.cited_by_api_url;
    if (!citedUrl && meta?.id) {
      citedUrl = `https://api.openalex.org/works/${encodeURIComponent(meta.id.split('/').pop())}/cited-by`;
    }
    if (!citedUrl) {
      return NextResponse.json({ counts: { academia: 0, industry: 0, government: 0, mixed: 0, unknown: 0 }, total: 0 });
    }
    const { counts, total } = await listCitingWithInstitutions(citedUrl);
    return NextResponse.json({ counts, total });
  } catch (e) {
    return NextResponse.json({ counts: { academia: 0, industry: 0, government: 0, mixed: 0, unknown: 0 }, total: 0, error: String(e) }, { status: 200 });
  }
}
