import requests
# Fetch ICLR 2025 submissions from OpenReview API v2 using openreview-py
# Usage: python fetch_iclr2025_openreview.py
# You will be prompted for your OpenReview username and password (not stored)

import openreview
from datetime import datetime, timezone
import getpass


# List of top 5 conferences and their 2025 venue IDs
VENUE_ID = "ICLR.cc/2025/Conference"
INVITATION_TYPES = ["Blind_Submission", "Submission"]


def ms_to_iso(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).isoformat()


def main():

    client = openreview.api.OpenReviewClient(
        baseurl="https://api2.openreview.net",
        username="ehasanov6@gatech.edu",
        password="@Azerbaijan2025"
    )
    total_records = 0
    print(f"\n========== ICLR ({VENUE_ID}) ==========")
    for invitation_type in INVITATION_TYPES:
        invitation = f"{VENUE_ID}/-/{invitation_type}"
        print(f"\nFetching submissions for {invitation} ...")
        try:
            submissions = client.get_all_notes(invitation=invitation)
        except Exception as e:
            print(f"  [Warning] Could not fetch submissions: {e}")
            continue
        print(f"Total submissions fetched: {len(submissions)}")
        if submissions:
            records = []
            for note in submissions:
                content = note.content
                # Only include most highly rated papers (Oral or Spotlight)
                venue_val = content.get('venue', {}).get('value', '')
                venue_val_lower = venue_val.lower()
                if not (venue_val_lower and 'iclr' in venue_val_lower and '2025' in venue_val_lower and ('oral' in venue_val_lower or 'spotlight' in venue_val_lower)):
                    continue
                title = content.get('title', {}).get('value')
                abstract = content.get('abstract', {}).get('value')
                authors_list = content.get('authors', {}).get('value')
                if isinstance(authors_list, list):
                    authors = authors_list
                else:
                    authors = [authors_list] if authors_list else None
                pub_ms = getattr(note, 'odate', None) or getattr(note, 'tcdate', None)
                publication_date_iso = ms_to_iso(pub_ms)
                records.append({
                    "id": note.id,
                    "number": getattr(note, "number", None),
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "publication_date": publication_date_iso
                })
            print(f"First 10 highly rated records (with citation counts from Semantic Scholar):")
            for rec in records[:10]:
                # Query Semantic Scholar API for citation count using DOI/arXiv if available, else title
                citation_count = 0
                doi = None
                arxiv_id = None
                # Try to extract DOI or arXiv ID from OpenReview note if present
                note_id = rec.get("id")
                note_obj = next((n for n in submissions if n.id == note_id), None)
                if note_obj:
                    content = note_obj.content
                    doi = content.get('doi', {}).get('value') if content.get('doi') else None
                    arxiv_id = content.get('arxiv', {}).get('value') if content.get('arxiv') else None
                try:
                    if doi:
                        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,citationCount"
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            citation_count = data.get('citationCount', 0)
                    elif arxiv_id:
                        url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields=title,citationCount"
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            citation_count = data.get('citationCount', 0)
                    elif rec["title"]:
                        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(rec['title'])}&fields=title,citationCount&limit=1"
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            papers = data.get('data', [])
                            if papers:
                                citation_count = papers[0].get('citationCount', 0)
                except Exception as e:
                    print(f"  [Warning] Citation lookup failed: {e}")
                rec["citation_count"] = citation_count
                print(rec)
            print(f"Total highly rated records for {invitation}: {len(records)}")
            total_records += len(records)
    print(f"\nTotal highly rated records for ICLR: {total_records}")

if __name__ == "__main__":
    main()
