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

async function openAlexFindWork({ doi, title, year, authors }) {
  try {
    let url = null;
    if (doi) url = `https://api.openalex.org/works/doi:${doi}`;
    else if (title) url = `https://api.openalex.org/works?filter=title.search:${encodeURIComponent(title)}&per_page=10`;
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
          const auths = (it?.authorships || [])
            .map((a) => a?.author?.display_name)
            .filter(Boolean)
            .join(", ");
          const aOk = authorsOverlap(authors, auths);
          return tOk && yOk && aOk;
        });
      }
      return match || null;
    }
    return j;
  } catch {
    return null;
  }
}

function classifyFromInstitutions(work) {
  const auths = Array.isArray(work?.authorships) ? work.authorships : [];
  const types = new Set();
  for (const a of auths) {
    const insts = Array.isArray(a?.institutions) ? a.institutions : [];
    for (const inst of insts) {
      const t = (inst?.type || inst?.ror?.type || "").toString().toLowerCase();
      if (t) types.add(t);
    }
  }
  const hasCompany = types.has("company") || types.has("forprofit") || types.has("business");
  const hasEducation = types.has("education") || types.has("university") || types.has("facility") || types.has("college");
  if (hasCompany && hasEducation) return "mixed";
  if (hasCompany) return "industry";
  if (hasEducation) return "academia";
  return "unknown";
}

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const doi = searchParams.get("doi") || undefined;
    const title = searchParams.get("title") || undefined;
    const authors = searchParams.get("authors") || undefined;
    const year = searchParams.get("year") || undefined;

    const work = await openAlexFindWork({ doi, title, year, authors });
    if (!work) return NextResponse.json({ sector: "unknown" });
    const sector = classifyFromInstitutions(work);
    return NextResponse.json({ sector, openalex_id: work?.id || null });
  } catch (e) {
    return NextResponse.json({ sector: "unknown", error: String(e) }, { status: 200 });
  }
}
