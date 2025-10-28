import { NextResponse } from "next/server";

function normalizeTitle(t) {
	return String(t || "")
		.toLowerCase()
		.replace(/[^a-z0-9\s]/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

export async function GET(req) {
	const { searchParams } = new URL(req.url);
	const rawDoi = searchParams.get("doi") || undefined;
	const title = searchParams.get("title") || undefined;
	const arxiv = searchParams.get("arxivId") || undefined;

	// If DOI provided, trust it
	if (rawDoi) return NextResponse.json({ doi: rawDoi, via: "input" });

	if (!title && !arxiv) return NextResponse.json({ doi: null }, { status: 400 });

	const normQ = normalizeTitle(title);

	// 1) Crossref by title
	if (title) {
		try {
			const r = await fetch(
		`https://api.crossref.org/works?rows=10&query.title=${encodeURIComponent(title)}`,
				{ cache: "no-store" }
			);
			if (r.ok) {
				const j = await r.json();
		const items = j?.message?.items || [];
		const match = items.find((i) => normalizeTitle(i?.title?.[0]) === normQ);
		if (match?.DOI) return NextResponse.json({ doi: match.DOI, via: "crossref" });
			}
		} catch {}
	}

	// 2) OpenAlex by title (or by arXiv)
	try {
		let r;
		if (arxiv) {
			r = await fetch(`https://api.openalex.org/works/arXiv:${arxiv}`, {
				cache: "no-store",
			});
			if (r.ok) {
				const j = await r.json();
				const doi = j?.doi ? j.doi.replace(/^https?:\/\/doi\.org\//i, "") : null;
				if (doi) return NextResponse.json({ doi, via: "openalex-arxiv" });
			}
		}
		if (title) {
			r = await fetch(
			`https://api.openalex.org/works?filter=title.search:${encodeURIComponent(title)}&per_page=10`,
				{ cache: "no-store" }
			);
			if (r.ok) {
				const j = await r.json();
			const items = j?.results || [];
			const match = items.find((i) => normalizeTitle(i?.title) === normQ);
			const doi = match?.doi ? match.doi.replace(/^https?:\/\/doi\.org\//i, "") : null;
			if (doi) return NextResponse.json({ doi, via: "openalex" });
			}
		}
	} catch {}

	// 3) Semantic Scholar by title
	try {
		const r = await fetch(
			`https://api.semanticscholar.org/graph/v1/paper/search?query=${encodeURIComponent(
				title || arxiv || ""
			)}&limit=5&fields=externalIds,title`,
			{ cache: "no-store" }
		);
			if (r.ok) {
			const j = await r.json();
				const items = j?.data || [];
				const match = items.find((i) => normalizeTitle(i?.title) === normQ);
				const doi = match?.externalIds?.DOI || null;
				if (doi) return NextResponse.json({ doi, via: "s2" });
		}
	} catch {}

	return NextResponse.json({ doi: null }, { status: 404 });
}

