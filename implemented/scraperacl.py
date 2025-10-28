
import requests
from bs4 import BeautifulSoup
import urllib3
import time
import json
# --- Supabase integration ---
import os
from supabase import create_client, Client

# Set these to your actual values or load from environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://rdqtckpkytaavxffskme.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_citation_count(title):
    # Query Semantic Scholar API for citation count by title
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(title)}&fields=citationCount,title&limit=1"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('data') and len(data['data']) > 0:
                paper = data['data'][0]
                # Check title match (case-insensitive, ignore whitespace)
                if paper.get('title') and paper['title'].strip().lower() == title.strip().lower():
                    return paper.get('citationCount', 0)
                else:
                    return paper.get('citationCount', 0)  # fallback: return top result's count
    except Exception as e:
        pass
    return None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_acl_2025():
    url = "https://aclanthology.org/events/acl-2025/"
    print("Fetching ACL 2025 event page...")
    resp = requests.get(url, verify=False)
    soup = BeautifulSoup(resp.text, "html.parser")
    paper_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only follow links to individual paper pages (not .pdf, .bib, etc.)
        if href.startswith("/2025.") and href.count('.') == 2 and not href.endswith(('.pdf', '.bib', '.xml', '.txt')):
            paper_links.append(href)
    print(f"Found {len(paper_links)} paper links on the event page.")
    papers = []
    count = 0
    for link in paper_links:
        paper_url = "https://aclanthology.org" + link
        abs_resp = requests.get(paper_url, verify=False)
        abs_soup = BeautifulSoup(abs_resp.text, "html.parser")
        # Title: <h2 id="title">
        title = None
        title_tag = abs_soup.find("h2", id="title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        # Skip proceedings/volume pages
        if not title or title.startswith("Proceedings of the"):
            continue
        # Authors: <p class="lead"> with <a> tags
        authors = None
        lead_p = abs_soup.find("p", class_="lead")
        if lead_p:
            authors = ", ".join([a.get_text(strip=True) for a in lead_p.find_all("a")])
        # Abstract
        abstract = None
        abstract_tag = abs_soup.find("div", class_="card-body acl-abstract")
        if abstract_tag:
            abstract = abstract_tag.get_text(strip=True)
        # Publication date
        pub_date_meta = abs_soup.find("meta", {"name": "citation_publication_date"})
        publication_date = pub_date_meta["content"] if pub_date_meta else None
        # Citation count
        citation_count = get_citation_count(title) if title else 0
        citation_count = citation_count or 0
        if citation_count > 0:
            # Validate publication_date format (YYYY-MM-DD)
            import re
            pub_date = publication_date or None
            if not pub_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", pub_date):
                pub_date = "2025-07-01"
            paper_data = {
                "title": title or 'N/A',
                "author": authors or 'N/A',
                "abstract": abstract or 'N/A',
                "publication_date": pub_date,
                "citation_number": citation_count,
                "conference_name": "ACL"
            }
            papers.append(paper_data)
            # --- Supabase insert ---
            try:
                supabase.table("papers").insert(paper_data).execute()
                print(f"[DB] Inserted: {title}")
            except Exception as e:
                print(f"[DB] Error inserting {title}: {e}")
    # No break: process all papers
    print("\nFetched papers with >0 citations:")
    for p in papers:
        print(p)

if __name__ == "__main__":
    fetch_acl_2025()
