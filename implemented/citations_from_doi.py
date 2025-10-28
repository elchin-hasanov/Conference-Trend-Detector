
from __future__ import annotations

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests


SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
OPENALEX_BASE = "https://api.openalex.org"


def normalize_input_identifier(raw: str) -> Dict[str, str]:
    """Return a dict with best-effort identifiers: doi and arxiv id if found.

    Accepts DOI URL, bare DOI, arXiv URL, or arXiv id; returns keys 'doi' and/or 'arxiv'.
    """
    out: Dict[str, str] = {}
    s = raw.strip()

    # If URL, try to extract DOI or arXiv id
    if s.lower().startswith("http"):
        # DOI via doi.org
        m = re.search(r"doi\.org/(.+)$", s, re.IGNORECASE)
        if m:
            out["doi"] = m.group(1).strip()
        # arXiv id in URL
        m2 = re.search(r"arxiv\.org/(abs|pdf)/([0-9]{4}\.[0-9]{5})(?:v\d+)?", s, re.IGNORECASE)
        if m2:
            out["arxiv"] = m2.group(2)
        return out

    # Bare arXiv id e.g. 2410.02113 or arXiv:2410.02113
    m3 = re.match(r"(?:arxiv:)?([0-9]{4}\.[0-9]{5})", s, re.IGNORECASE)
    if m3:
        out["arxiv"] = m3.group(1)
        return out

    # Otherwise assume bare DOI
    if "/" in s:
        out["doi"] = s
    return out


def s2_headers() -> Dict[str, str]:
    key = os.environ.get("S2_API_KEY")
    return {"x-api-key": key} if key else {}


def s2_get_paper_identifier(doi: Optional[str], arxiv: Optional[str]) -> Optional[str]:
    """Return an identifier usable in S2 paths, preferring DOI then arXiv, else None."""
    if doi:
        return f"DOI:{doi}"
    if arxiv:
        return f"arXiv:{arxiv}"
    return None


def s2_get_paper_meta(paper_id: str) -> Optional[Dict]:
    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}"
    fields = [
        "title",
        "year",
        "venue",
        "authors",
        "externalIds",
        "url",
        "openAccessPdf",
        "citationCount",
        "influentialCitationCount",
    ]
    try:
        r = requests.get(url, params={"fields": ",".join(fields)}, headers=s2_headers(), timeout=20)
        if r.status_code == 200:
            return r.json()
        return None
    except requests.RequestException:
        return None


def s2_list_citations(paper_id: str, max_pages: int = 50, page_size: int = 100) -> List[Dict]:
    """Paginate through S2 citations endpoint and return list of citing papers."""
    results: List[Dict] = []
    # Include publicationDate to extract month/year
    fields = "title,year,venue,authors,externalIds,url,publicationDate"
    headers = s2_headers()
    for page in range(max_pages):
        offset = page * page_size
        url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}/citations"
        try:
            r = requests.get(
                url,
                params={"fields": fields, "limit": page_size, "offset": offset},
                headers=headers,
                timeout=30,
            )
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get("data", [])
            for it in items:
                cp = it.get("citingPaper", {})
                if cp:
                    results.append(cp)
            if len(items) < page_size:
                break
            # Light backoff to be polite
            time.sleep(0.2)
        except requests.RequestException:
            break
    return results


def openalex_get_paper_meta(doi: Optional[str], arxiv: Optional[str]) -> Optional[Dict]:
    try:
        if doi:
            url = f"{OPENALEX_BASE}/works/doi:{doi}"
        elif arxiv:
            url = f"{OPENALEX_BASE}/works/arXiv:{arxiv}"
        else:
            return None
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return r.json()
        return None
    except requests.RequestException:
        return None


def openalex_list_citations(work: Dict, per_page: int = 200, max_pages: int = 50) -> List[Dict]:
    cite_url = work.get("cited_by_api_url")
    if not cite_url:
        return []
    results: List[Dict] = []
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(cite_url, params={"per_page": per_page, "page": page}, timeout=30)
            if r.status_code != 200:
                break
            data = r.json()
            results.extend(data.get("results", []))
            if len(data.get("results", [])) < per_page:
                break
            time.sleep(0.2)
        except requests.RequestException:
            break
    return results


def parse_month_year(date_str: Optional[str], fallback_year: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """Parse a date string into (year, month). Accepts YYYY, YYYY-MM, or YYYY-MM-DD.
    If missing, use fallback_year with month=1 if provided.
    """
    if not date_str and fallback_year:
        try:
            return int(fallback_year), 1
        except Exception:
            return None
    if not date_str:
        return None
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.year, dt.month
        except ValueError:
            continue
    # Last resort: try to slice
    try:
        year = int(s[:4])
        month = int(s[5:7]) if len(s) >= 7 and s[4] in ("-", "/") else 1
        return year, month
    except Exception:
        return None


def aggregate_citations_by_month(citations: List[Dict], source: str) -> List[Tuple[str, int]]:
    """Return list of (YYYY-MM, count) sorted ascending by month."""
    counts: Dict[str, int] = {}
    if source == "s2":
        for p in citations:
            year = p.get("year")
            pub_date = p.get("publicationDate")  # e.g., '2025-07-10'
            ym = parse_month_year(pub_date, fallback_year=year)
            if ym:
                key = f"{ym[0]:04d}-{ym[1]:02d}"
                counts[key] = counts.get(key, 0) + 1
    else:
        for p in citations:
            year = p.get("publication_year")
            pub_date = p.get("publication_date")  # e.g., '2025-07-10'
            ym = parse_month_year(pub_date, fallback_year=year)
            if ym:
                key = f"{ym[0]:04d}-{ym[1]:02d}"
                counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[0])


def render_chart(month_counts: List[Tuple[str, int]], outfile: Optional[str] = None) -> Optional[str]:
    """Render a bar chart to outfile using matplotlib if available; otherwise print ASCII bars.
    Returns the outfile path if saved, else None.
    """
    if not month_counts:
        print("No month/year data available for citations.")
        return None

    # Try matplotlib first
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt

        labels = [m for m, _ in month_counts]
        values = [c for _, c in month_counts]
        fig, ax = plt.subplots(figsize=(max(6, min(18, len(labels) * 0.4)), 4))
        ax.bar(labels, values, color="#4C78A8")
        ax.set_title("Citations per Month")
        ax.set_xlabel("Month")
        ax.set_ylabel("Count")
        for i, v in enumerate(values):
            ax.text(i, v + max(values) * 0.01, str(v), ha='center', va='bottom', fontsize=8)
        plt.xticks(rotation=60, ha='right')
        plt.tight_layout()
        outfile = outfile or "citations_timeline.png"
        plt.savefig(outfile, dpi=150)
        plt.close(fig)
        return outfile
    except Exception:
        # ASCII fallback
        print("\nCitations per Month (ASCII):")
        max_val = max(c for _, c in month_counts)
        scale = 50 / max_val if max_val > 0 else 1
        for m, c in month_counts:
            bar = "#" * max(1, int(c * scale))
            print(f"{m} | {bar} ({c})")
        return None


def format_authors_s2(authors: List[Dict]) -> str:
    names = [a.get("name", "").strip() for a in authors or [] if a.get("name")]
    return ", ".join(names[:10]) + (" et al." if len(names) > 10 else "")


def format_authors_openalex(authorships: List[Dict]) -> str:
    names = []
    for a in authorships or []:
        author = a.get("author", {})
        n = author.get("display_name") or author.get("display_name_alternatives", [None])[0]
        if n:
            names.append(n)
    return ", ".join(names[:10]) + (" et al." if len(names) > 10 else "")


def print_summary_and_citations(meta: Dict, citations: List[Dict], source: str, chart_path: Optional[str] = None) -> None:
    print("\n=== Source paper ===")
    print(f"Title: {meta.get('title')}")
    year = meta.get('year') or meta.get('publication_year')
    venue = meta.get('venue') or meta.get('host_venue', {}).get('display_name')
    print(f"Year: {year}  Venue: {venue}")
    print(f"Citations found: {len(citations)}  (via {source})\n")

    # Sort by year desc, then title
    def get_year_s2(p: Dict) -> int:
        y = p.get('year')
        try:
            return int(y)
        except (TypeError, ValueError):
            return -1

    if source == "s2":
        citations_sorted = sorted(citations, key=lambda p: (get_year_s2(p), (p.get('title') or '').lower()), reverse=True)
    for p in citations_sorted:
            title = p.get('title') or '(no title)'
            authors = format_authors_s2(p.get('authors'))
            year = p.get('year')
            venue = p.get('venue')
            exids = p.get('externalIds') or {}
            doi = exids.get('DOI')
            arx = exids.get('ArXiv')
            url = p.get('url')
            ident = f"DOI:{doi}" if doi else (f"arXiv:{arx}" if arx else (url or ''))
            print(f"- {title}\n  Authors: {authors}\n  Year: {year}  Venue: {venue}\n  Id: {ident}\n")
    else:
        # OpenAlex
        def get_year_oa(p: Dict) -> int:
            y = p.get('publication_year')
            try:
                return int(y)
            except (TypeError, ValueError):
                return -1
        citations_sorted = sorted(citations, key=lambda p: (get_year_oa(p), (p.get('title') or '').lower()), reverse=True)
    for p in citations_sorted:
            title = p.get('title') or '(no title)'
            authors = format_authors_openalex(p.get('authorships'))
            year = p.get('publication_year')
            venue = (p.get('host_venue') or {}).get('display_name')
            doi = p.get('doi')
            oa_id = p.get('id')
            print(f"- {title}\n  Authors: {authors}\n  Year: {year}  Venue: {venue}\n  Id: {doi or oa_id}\n")

    # Build and render monthly chart
    month_counts = aggregate_citations_by_month(citations, source)
    if month_counts:
        print("\nCitations per month:")
        for m, c in month_counts:
            print(f"  {m}: {c}")
        out = render_chart(month_counts, chart_path)
        if out:
            print(f"\nSaved chart to: {out}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="List citing papers for a given DOI/arXiv id and plot citation months")
    parser.add_argument("identifier", nargs="?", help="DOI/arXiv id or URL (default: 10.48550/arXiv.2410.02113)")
    parser.add_argument("--id", dest="alt_id", help="Explicit S2 path-style id e.g. DOI:10.1234/foo or arXiv:2410.02113")
    parser.add_argument("--chart", dest="chart", help="Output PNG path for monthly citations chart (default: citations_timeline.png)")
    args = parser.parse_args(argv)

    raw = args.identifier or "10.48550/arXiv.2410.02113"
    ids = normalize_input_identifier(raw)

    # If explicit id provided, try that first
    s2_path_id = args.alt_id or s2_get_paper_identifier(ids.get("doi"), ids.get("arxiv"))

    # Try Semantic Scholar first
    s2_meta = None
    citations = []
    source = None
    if s2_path_id:
        s2_meta = s2_get_paper_meta(s2_path_id)
        if s2_meta:
            citations = s2_list_citations(s2_path_id)
            source = "s2"

    # Fallback to OpenAlex
    if not citations:
        oa_meta = openalex_get_paper_meta(ids.get("doi"), ids.get("arxiv"))
        if not oa_meta:
            print("Could not resolve the identifier via Semantic Scholar or OpenAlex.", file=sys.stderr)
            return 2
        citations = openalex_list_citations(oa_meta)
        # Convert OpenAlex meta into a minimal meta dict for printing
        s2_meta = {
            "title": oa_meta.get("title"),
            "year": oa_meta.get("publication_year"),
            "venue": (oa_meta.get("host_venue") or {}).get("display_name"),
        }
        source = "openalex"

    print_summary_and_citations(s2_meta or {}, citations, source or "openalex", chart_path=args.chart or "citations_timeline.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
