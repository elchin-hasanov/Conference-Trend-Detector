import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# --- Supabase integration ---
import os
from supabase import create_client, Client

# Set these to your actual values or load from environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://rdqtckpkytaavxffskme.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJkcXRja3BreXRhYXZ4ZmZza21lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk3NTc3NjYsImV4cCI6MjA3NTMzMzc2Nn0.ROp8W1PSQt7vo5FNM8G3Eobh3ebXw82HTEmxJONOo1g')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_cvpr_2025():
    print("[INFO] Starting CVPR 2025 scraper...")
    url = "https://openaccess.thecvf.com/CVPR2025?day=all"  # Update if 2025 is not available
    resp = requests.get(url, verify=False)
    soup = BeautifulSoup(resp.text, "html.parser")
    papers = soup.select("dt.ptitle a")
    results = []
    import re
    import time
    def get_arxiv_abstract_and_citations(arxiv_url):
        abs_url = arxiv_url.replace('pdf', 'abs') if 'pdf' in arxiv_url else arxiv_url
        abs_resp = requests.get(abs_url)
        abs_soup = BeautifulSoup(abs_resp.text, "html.parser")
        # Abstract
        abstract = ""
        abstract_tag = abs_soup.find("blockquote", class_="abstract")
        if abstract_tag:
            abstract = abstract_tag.get_text(strip=True).replace('Abstract:','').strip()
        # Authors from arXiv
        authors = ""
        authors_div = abs_soup.find("div", class_="authors")
        if authors_div:
            author_links = authors_div.find_all("a")
            authors = ", ".join([a.get_text(strip=True) for a in author_links])
        # Citation count from Semantic Scholar using arXiv id
        arxiv_id_match = re.search(r'arxiv.org/abs/([\w.]+)', abs_url)
        citation_count = 0
        if arxiv_id_match:
            arxiv_id = arxiv_id_match.group(1)
            sem_url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=citationCount"
            try:
                sem_resp = requests.get(sem_url)
                if sem_resp.status_code == 200:
                    sem_data = sem_resp.json()
                    citation_count = sem_data.get('citationCount', 0)
            except Exception:
                pass
        return abstract, citation_count

    printed = 0
    for paper in papers:
        title = paper.get_text(strip=True)
        paper_url = "https://openaccess.thecvf.com" + paper['href']
        abs_resp = requests.get(paper_url, verify=False)
        abs_soup = BeautifulSoup(abs_resp.text, "html.parser")
        # Find arXiv link
        arxiv_link = None
        for a in abs_soup.find_all('a', href=True):
            if 'arxiv.org' in a['href']:
                arxiv_link = a['href']
                break
        if not arxiv_link:
            continue
        # Authors from arXiv (fallback if not found on CVPR page)
        abstract, citation_count = get_arxiv_abstract_and_citations(arxiv_link)
        authors = ""
        authors_div = abs_soup.select_one("div.authors")
        if authors_div:
            author_links = authors_div.find_all("a")
            authors = ", ".join([a.get_text(strip=True) for a in author_links])
        if not authors:
            # fallback to arXiv authors
            abs_arxiv_resp = requests.get(arxiv_link)
            abs_arxiv_soup = BeautifulSoup(abs_arxiv_resp.text, "html.parser")
            authors_div_arxiv = abs_arxiv_soup.find("div", class_="authors")
            if authors_div_arxiv:
                author_links_arxiv = authors_div_arxiv.find_all("a")
                authors = ", ".join([a.get_text(strip=True) for a in author_links_arxiv])
        pub_date = "2025-06-01"
        if citation_count > 0:
            paper_data = {
                "title": title or 'N/A',
                "author": authors or 'N/A',
                "abstract": abstract or 'N/A',
                "publication_date": pub_date,
                "citation_number": citation_count,
                "conference_name": "CVPR"
            }
            results.append(paper_data)
            # --- Supabase insert ---
            try:
                supabase.table("papers").insert(paper_data).execute()
                print(f"[DB] Inserted: {title}")
            except Exception as e:
                print(f"[DB] Error inserting {title}: {e}")
            printed += 1
        time.sleep(0.5)
    print("\nFetched papers with >0 citations:")
    for p in results:
        print(p)

if __name__ == "__main__":
    fetch_cvpr_2025()
