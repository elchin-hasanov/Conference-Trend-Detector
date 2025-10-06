import time
import warnings
from urllib3.exceptions import InsecureRequestWarning
import requests
from bs4 import BeautifulSoup

# --- Supabase integration ---
import os
from supabase import create_client, Client

# Set these to your actual values or load from environment variables
SUPABASE_URL = "https://rdqtckpkytaavxffskme.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJkcXRja3BreXRhYXZ4ZmZza21lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk3NTc3NjYsImV4cCI6MjA3NTMzMzc2Nn0.ROp8W1PSQt7vo5FNM8G3Eobh3ebXw82HTEmxJONOo1g"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_citation_count(title):
	"""Query Semantic Scholar API for citation count by paper title."""
	api_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(title)}&fields=citationCount,title&limit=1"
	try:
		resp = requests.get(api_url, timeout=10)
		if resp.status_code == 200:
			data = resp.json()
			if data.get('data') and len(data['data']) > 0:
				return data['data'][0].get('citationCount', 'N/A')
	except Exception as e:
		pass
	return 'N/A'

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def scrape_aaai_proceedings():
	print("\n--- AAAI First 5 Papers from Last Year's Proceedings ---")
	proceedings_url = "https://ojs.aaai.org/index.php/AAAI/issue/archive"
	headers = {
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
	}
	resp = requests.get(proceedings_url, headers=headers, verify=False)
	soup = BeautifulSoup(resp.text, 'html.parser')

	# Find the link to the most recent full proceedings (should be the first in the list)
	issue_links = soup.select('div.obj_issue_summary a.title')
	if not issue_links:
		print("Could not find proceedings links.")
		return
	latest_issue_url = issue_links[0]['href']
	if not latest_issue_url.startswith('http'):
		latest_issue_url = 'https://ojs.aaai.org' + latest_issue_url

	# Get the list of article links from the latest proceedings
	resp = requests.get(latest_issue_url, headers=headers, verify=False)
	soup = BeautifulSoup(resp.text, 'html.parser')
	# Find all <a> tags with href containing '/article/view/'
	articles = []
	seen = set()
	for a in soup.find_all('a', href=True):
		href = a['href']
		title = a.text.strip()
		# Only consider HTML article pages, skip PDFs, downloads, and navigation links
		if (
			'/article/view/' in href
			and not href.endswith('.pdf')
			and '/article/download/' not in href
			and href not in seen
			and title
			and title.lower() != 'pdf'
			and not title.isdigit()
		):
			seen.add(href)
			# Authors are usually in the next sibling or parent
			authors = 'N/A'
			parent = a.find_parent()
			if parent:
				next_sib = parent.find_next_sibling()
				if next_sib and next_sib.text:
					# Remove page numbers and whitespace
					authors_candidate = next_sib.text.strip()
					if any(c.isalpha() for c in authors_candidate):
						authors = authors_candidate
			articles.append((href, title, authors))
	# No break: process all valid articles
	if not articles:
		print("Could not find article links in proceedings. Printing a snippet of the HTML for debugging:\n")
		print(soup.prettify()[:3000])  # Print the first 3000 characters for inspection
		return

	printed = 0
	for i, (article_url, title, authors) in enumerate(articles):
		if not article_url.startswith('http'):
			article_url = 'https://ojs.aaai.org' + article_url
		abstract, pub_date = scrape_aaai_abstract_pubdate(article_url, headers)
		citation_count = get_citation_count(title)
		if citation_count == 'N/A':
			citation_count = 0
		if isinstance(citation_count, str):
			try:
				citation_count = int(citation_count)
			except Exception:
				citation_count = 0

		if citation_count > 0:
			# --- Supabase insert ---
			paper_data = {
				"title": title or 'N/A',
				"author": authors or 'N/A',
				"abstract": abstract or 'N/A',
				"publication_date": pub_date or None,
				"citation_number": citation_count,
				"conference_name": "AAAI"
			}
			try:
				supabase.table("papers").insert(paper_data).execute()
				print(f"[DB] Inserted: {title}")
			except Exception as e:
				print(f"[DB] Error inserting {title}: {e}")

			printed += 1
			print(f"\n--- Paper {printed} ---")
			print(f"Title: {title or 'N/A'}\nAuthors: {authors or 'N/A'}\nAbstract: {abstract or 'N/A'}\nPublication Date: {pub_date or 'N/A'}\nCitations: {citation_count}")
		time.sleep(1)  # Be polite to the API
def scrape_aaai_abstract_pubdate(url, headers):
	resp = requests.get(url, headers=headers, verify=False)
	soup = BeautifulSoup(resp.text, 'html.parser')
	# Abstract: <section class="item abstract">
	abstract = 'N/A'
	abs_section = soup.find('section', class_='item abstract')
	if abs_section:
		# Get all text after the heading
		abs_heading = abs_section.find(['h2', 'h3', 'strong'])
		if abs_heading:
			abs_heading.extract()
		abstract = abs_section.get_text(strip=True)
	# Publication date: <div class="item published"> ... <span>DATE</span>
	pub_date = 'N/A'
	pub_div = soup.find('div', class_='item published')
	if pub_div:
		pub_span = pub_div.find('span')
		if pub_span:
			pub_date = pub_span.text.strip()
	return abstract, pub_date
def scrape_aaai_abstract_keywords(url, headers):
	resp = requests.get(url, headers=headers, verify=False)
	soup = BeautifulSoup(resp.text, 'html.parser')
	# Try meta tags first
	def get_meta(name):
		tag = soup.find('meta', {'name': name})
		return tag['content'].strip() if tag and tag.has_attr('content') else ''
	abstract = get_meta('citation_abstract') or get_meta('description')
	keywords = get_meta('keywords')
	# Fallback: extract abstract from visible HTML
	if not abstract or abstract == 'N/A':
		abstract_heading = soup.find(lambda tag: tag.name in ['h2', 'h3', 'strong'] and 'abstract' in tag.text.lower())
		if abstract_heading:
			next_tag = abstract_heading.find_next_sibling(['p', 'div'])
			if next_tag:
				abstract = next_tag.text.strip()
			else:
				parent_next = abstract_heading.parent.find_next_sibling(['p', 'div'])
				if parent_next:
					abstract = parent_next.text.strip()
	# Fallback: extract keywords from visible HTML
	if not keywords or keywords == 'N/A':
		kw_heading = soup.find(lambda tag: tag.name in ['h2', 'h3', 'strong'] and 'keyword' in tag.text.lower())
		if kw_heading:
			next_tag = kw_heading.find_next_sibling(['p', 'div'])
			if next_tag:
				keywords = next_tag.text.strip()
			else:
				parent_next = kw_heading.parent.find_next_sibling(['p', 'div'])
				if parent_next:
					keywords = parent_next.text.strip()
	return abstract, keywords
def scrape_aaai_paper(url, headers):
	resp = requests.get(url, headers=headers, verify=False)
	soup = BeautifulSoup(resp.text, 'html.parser')
	def get_meta(name):
		tag = soup.find('meta', {'name': name})
		return tag['content'].strip() if tag and tag.has_attr('content') else ''
	title = get_meta('citation_title')
	abstract = get_meta('citation_abstract') or get_meta('description')
	authors = ', '.join([meta['content'].strip() for meta in soup.find_all('meta', {'name': 'citation_author'}) if meta.has_attr('content')])
	keywords = get_meta('keywords')
	pub_date = get_meta('citation_publication_date')

	# Fallback: extract abstract from visible HTML
	if not abstract or abstract == 'N/A':
		# Look for a heading with 'Abstract' and get the next sibling
		abstract_heading = soup.find(lambda tag: tag.name in ['h2', 'h3', 'strong'] and 'abstract' in tag.text.lower())
		if abstract_heading:
			# Try next sibling or parent/next element
			next_tag = abstract_heading.find_next_sibling(['p', 'div'])
			if next_tag:
				abstract = next_tag.text.strip()
			else:
				# Try parent next
				parent_next = abstract_heading.parent.find_next_sibling(['p', 'div'])
				if parent_next:
					abstract = parent_next.text.strip()

	# Fallback: extract publication date from visible HTML
	if not pub_date or pub_date == 'N/A':
		pub_label = soup.find(lambda tag: tag.name in ['div', 'span', 'p'] and 'published' in tag.text.lower())
		if pub_label:
			# Try to extract a date from the text
			import re
			match = re.search(r'\d{4}-\d{2}-\d{2}', pub_label.text)
			if match:
				pub_date = match.group(0)

	# If still missing, print a snippet for debugging
	if not abstract or not pub_date or abstract == 'N/A' or pub_date == 'N/A':
		print("[DEBUG] Could not extract all fields from visible HTML. Printing a snippet of the HTML for inspection:\n")
		print(soup.prettify()[:2000])

	print(f"Title: {title or 'N/A'}\nAbstract: {abstract or 'N/A'}\nAuthors: {authors or 'N/A'}\nKeywords: {keywords or 'N/A'}\nPublication Date: {pub_date or 'N/A'}")

if __name__ == "__main__":
	scrape_aaai_proceedings()
