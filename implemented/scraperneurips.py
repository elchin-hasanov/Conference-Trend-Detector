

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

import time
def get_citation_count(title, authors):
    # Query Semantic Scholar API for citation count by title and authors
    import requests
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(title)}&fields=citationCount,title,authors&limit=1"
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
    except Exception:
        pass
    return 0

def fetch_neurips_2025():
    print("[INFO] Starting NeurIPS 2025 scraper...")
    url = "https://papers.nips.cc/paper_files/paper/2024"  # Updated to 2024 proceedings
    resp = requests.get(url, verify=False)
    if resp.status_code != 200:
        print(f"Could not fetch NeurIPS 2025 proceedings page: {url} (status {resp.status_code})")
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    papers = soup.select("li a")
    if not papers:
        print("No papers found on the NeurIPS 2025 proceedings page. The page structure may have changed or the proceedings are not yet available.")
        return
    results = []
    for paper in papers:
        title = paper.get_text(strip=True)
        paper_url = "https://papers.nips.cc" + paper['href']
        abs_resp = requests.get(paper_url, verify=False)
        abs_soup = BeautifulSoup(abs_resp.text, "html.parser")
        # Authors: <h4>Authors</h4> followed by <p><i>...</i></p>
        authors = ""
        h4_authors = abs_soup.find("h4", string="Authors")
        if h4_authors:
            p_authors = h4_authors.find_next_sibling("p")
            if p_authors:
                i_authors = p_authors.find("i")
                if i_authors:
                    authors = i_authors.get_text(strip=True)
        # Abstract: <h4>Abstract</h4> followed by <p>...</p>
        abstract = ""
        h4_abstract = abs_soup.find("h4", string="Abstract")
        if h4_abstract:
            p_abstract = h4_abstract.find_next_sibling("p")
            if p_abstract:
                abstract = p_abstract.get_text(strip=True)
        # Publication date: try meta tag
        pub_date = "2025-12-01"
        meta_date = abs_soup.find("meta", {"name": "citation_publication_date"})
        if meta_date:
            pub_date = meta_date["content"]
        # Only print if at least one field is non-empty
        if title or authors or abstract or pub_date:
            citations = get_citation_count(title, authors)
            if citations > 0:
                paper_data = {
                    "title": title or 'N/A',
                    "author": authors or 'N/A',
                    "abstract": abstract or 'N/A',
                    "publication_date": pub_date,
                    "citation_number": citations,
                    "conference_name": "NeurIPS"
                }
                results.append(paper_data)
                # --- Supabase insert ---
                try:
                    supabase.table("papers").insert(paper_data).execute()
                    print(f"[DB] Inserted: {title}")
                except Exception as e:
                    print(f"[DB] Error inserting {title}: {e}")
            time.sleep(0.5)
    print("\nFetched papers with >0 citations:")
    for p in results:
        print(p)

if __name__ == "__main__":
    fetch_neurips_2025()
