import os
import re
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer  # added TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN


# ===================== Config =====================
DATASET_PATH = os.environ.get(
    "PAPERS_CSV",
    os.path.join(os.path.dirname(__file__), "papers_rows.csv")
)

EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-mpnet-base-v2"  # Upgraded for better quality
)

# Larger -> fewer, bigger clusters (usually fewer outliers initially)
MIN_CLUSTER_SIZE = int(os.environ.get("MIN_CLUSTER_SIZE", "3"))  # Reduced for more granular topics

# UMAP parameters for dimensionality reduction
UMAP_N_NEIGHBORS = int(os.environ.get("UMAP_N_NEIGHBORS", "15"))
UMAP_N_COMPONENTS = int(os.environ.get("UMAP_N_COMPONENTS", "50"))
UMAP_MIN_DIST = float(os.environ.get("UMAP_MIN_DIST", "0.0"))

# Words to exclude from topic labels (kept lowercase)
GENERIC = {
    "paper","study","work","approach","method","methods","technique","techniques",
    "model","models","language","large","vision","image","images","video","videos",
    "neural","network","networks","deep","learning","data","task","tasks","system","systems",
    "dataset","datasets","framework","benchmark","results","based","using","towards",
    "analysis","problem","problems","novel","state","art","field","general","performance",
    "generation","generative","representation","representations","understanding","understand",
    "algorithm","algorithms","adversarial","attack","attacks","graph","graphs","diffusion",
    "gaussian","gaussians","llm","llms","multimodal","multi","view","views","scene","scenes",
    "modeling","modelling","transformer","transformers","pretraining","pre-trained","pretrained",
    "zero","shot","zero-shot","few","shot","few-shot","self","supervised","self-supervised",
    "3d","2d","real","time","real-time","online","offline","robust","robustness","efficient",
    "improving","improved","improves","theory","theoretical",
    "learning-based","foundation","world","document","documents","object","objects",
    "semantic","segmentation","classification","retrieval","editing","edit","edits",
    "control","controls","mamba","video-language","vision-language","text","texts",
    "prompt","prompts","prompting","mining","distillation","regularization","regularizer",
    "prior","priors","bayesian","ctfidf","topic","topics","keyword","keywords",
    "et","al","et al","al."
}

EXTRA_STOP = {"et", "al", "et al", "al."}  # for vectorizer stopwords


# ===================== Helpers =====================
def preprocess_text(text):
    """Enhanced text preprocessing for academic papers."""
    if not text or pd.isna(text):
        return ""
    
    # Remove citations, URLs, special academic notation
    text = re.sub(r'\[.*?\]|\(.*?\)|https?://\S+', '', str(text))
    text = re.sub(r'[^\w\s\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
    return text.lower().strip()

def safe_stem(w: str) -> str:
    """Tiny stemmer to de-duplicate variants without extra deps."""
    w = w.lower()
    w = re.sub(r"[^a-z0-9\-]+", "", w)
    for suf in ["ing","edly","ed","ly","ies","s"]:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            if suf == "ies":
                return w[:-3] + "y"
            return w[:-len(suf)]
    return w

def is_generic(token: str) -> bool:
    t = token.lower().strip()
    t = re.sub(r"[^a-z0-9\-]+", " ", t).strip()
    return t in GENERIC

def unique_top_terms(candidates, k=5):
    """
    Pick k non-redundant terms:
    - drop generic words
    - drop very short tokens
    - avoid substring and stem collisions
    """
    chosen = []
    stems = set()
    for term, _score in candidates:
        term = term.strip().lower()
        if not term or is_generic(term) or len(term) < 3:
            continue
        if any(term in c or c in term for c in chosen):
            continue
        st = safe_stem(term)
        if st in stems:
            continue
        stems.add(st)
        chosen.append(term)
        if len(chosen) == k:
            break
    return chosen

def print_cluster(header, items):
    """Print a cluster header and its items.

    items: list of either titles (str) or (title, citation_number) tuples.
    """
    print(f"{header} — {len(items)} papers")
    for it in items:
        if isinstance(it, tuple) and len(it) >= 2:
            title, cites = it[0], it[1]
            cite_str = "N/A"
            try:
                if cites is not None and not (isinstance(cites, float) and np.isnan(cites)):
                    # print as integer if whole number, otherwise with no decimals
                    cval = float(cites)
                    cite_str = f"{int(cval)}" if cval.is_integer() else f"{cval:.0f}"
            except Exception:
                pass
            print(f"  - {title} (citations: {cite_str})")
        else:
            print(f"  - {it}")
    print()


# ---------- Summary utilities (NEW) ----------
JARGON_MAP = {
    r"\bstate[- ]?of[- ]the[- ]art\b": "leading-edge",
    r"\bSOTA\b": "leading-edge",
    r"\bbenchmark(s)?\b": "standard tests",
    r"\brobust(ness)?\b": "reliable",
    r"\bgeneralization\b": "perform well in new situations",
    r"\bmodalit(y|ies)\b": "data types",
    r"\bframework\b": "approach",
    r"\barchitecture\b": "design",
    r"\boptimization\b": "improvement",
    r"\binference\b": "running the model",
    r"\bthroughput\b": "processing speed",
    r"\blatenc(y|ies)\b": "delay",
    r"\bscal(able|ability)\b": "scale to bigger problems",
    r"\bparameter(s)?\b": "settings",
    r"\bpre[- ]?training\b": "training in advance",
    r"\bself[- ]?supervised\b": "learn from raw data",
    r"\bzero[- ]?shot\b": "without task-specific training",
    r"\bfew[- ]?shot\b": "with very little training data",
    r"\bGaussian Splatting\b": "a fast 3D scene technique",
    r"\bLLM(s)?\b": "large AI models",
    r"\btransformer(s)?\b": "a popular AI model design",
}
IMPACT_TERMS = {
    "industry","business","product","deployment","real-world","real world","application","applications",
    "economy","economic","cost","energy","speed","scal","safety","healthcare","robot","autonomous",
    "finance","manufacturing","commerce","content","security","privacy"
}

def _simplify_jargon(text: str) -> str:
    s = text
    for pat, repl in JARGON_MAP.items():
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()

def generate_cluster_summary(
    texts: list[str],
    keywords: list[str],
    n_sentences: int = 2,
    max_chars: int = 350,
    mmr_lambda: float = 0.6,
) -> str:
    """
    Build a brief, non-technical summary for a cluster.
    - Collect candidate sentences from abstracts.
    - Score by (relevance to keywords + centrality) with an MMR-style diversity penalty.
    - Prefer sentences that hint at real-world impact.
    - Lightly de-jargonize the final text.
    """
    if not texts:
        return ""

    # 1) Candidate sentence extraction
    candidates: list[str] = []
    for doc in texts:
        if not doc:
            continue
        parts = re.split(r"(?<=[.!?])\s+", doc.strip())
        for s in parts:
            s = s.strip()
            if 25 <= len(s) <= 350:
                candidates.append(s)

    # Fallback: chunk a few longer lines if splitting failed
    if not candidates:
        for doc in texts:
            t = re.sub(r"\s+", " ", (doc or "")).strip()
            step, win = 160, 200
            for i in range(0, len(t), step):
                chunk = t[i:i+win].strip()
                if 60 <= len(chunk) <= 350:
                    candidates.append(chunk)
                if len(candidates) >= 20:
                    break
            if len(candidates) >= 20:
                break

    # Remove dupes while preserving order
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return _simplify_jargon("This group of papers explores " + ", ".join((keywords or [])[:4]) + ".")

    # 2) TF-IDF encoding for relevance/centrality
    tfidf = TfidfVectorizer(stop_words="english", max_df=0.9, min_df=1, ngram_range=(1, 2))
    X = tfidf.fit_transform(candidates)

    # Build a soft query from keywords (or first few sentences if no keywords)
    query_text = " ".join((keywords or [])[:8]) if keywords else " ".join(candidates[:3])
    q = tfidf.transform([query_text])

    # Relevance to query (normalize)
    rel = (X @ q.T).toarray().ravel()
    if rel.max() > 0:
        rel = rel / (rel.max() + 1e-9)

    # Sentence centrality (similarity to others)
    S = (X @ X.T).toarray()
    row_max = S.max(axis=1) + 1e-9
    S = (S.T / row_max).T
    centrality = S.mean(axis=1)

    # 3) MMR-style greedy selection (relevance + centrality − redundancy)
    selected_idx: list[int] = []
    pool = list(range(len(candidates)))
    wanted = max(1, n_sentences)

    while len(selected_idx) < wanted and pool:
        best_i, best_score = None, -1e9
        for i in pool:
            div_pen = max((S[i, j] for j in selected_idx), default=0.0)  # diversity penalty
            impact_bonus = 0.15 if any(t in candidates[i].lower() for t in IMPACT_TERMS) else 0.0
            score = (0.65 * rel[i]) + (0.35 * centrality[i]) - (1 - mmr_lambda) * div_pen + impact_bonus
            if score > best_score:
                best_score, best_i = score, i
        selected_idx.append(best_i)
        pool.remove(best_i)

    picked = [candidates[i] for i in selected_idx if i is not None]

    # 4) Light de-jargon + gentle cleanup
    picked = [_simplify_jargon(s) for s in picked]
    text = " ".join(picked)[:max_chars].rstrip()
    if len(text) >= max_chars:
        text += "…"
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\([^)]{0,25}\)", "", text)  # drop tiny acronym-asides
    return text
# ---------- end Summary utilities (NEW) ----------


# ===================== Load data =====================
if not os.path.exists(DATASET_PATH):
    raise FileNotFoundError(
        f"Could not find dataset at '{DATASET_PATH}'. "
        f"Set PAPERS_CSV env var or adjust DATASET_PATH."
    )

print(f"Using dataset: {DATASET_PATH}")
df = pd.read_csv(DATASET_PATH)

# Expect 'title' and 'abstract'
for col in ["title", "abstract"]:
    if col not in df.columns:
        raise ValueError("CSV must include 'title' and 'abstract' columns")

df["title"] = df["title"].fillna("").astype(str)
df["abstract"] = df["abstract"].fillna("").astype(str)
# Coerce citations to numeric for aggregation/sorting
if "citation_number" in df.columns:
    df["citation_number"] = pd.to_numeric(df["citation_number"], errors="coerce")

# Enhanced preprocessing
df["title_clean"] = df["title"].apply(preprocess_text)
df["abstract_clean"] = df["abstract"].apply(preprocess_text)
docs = (df["title_clean"] + ". " + df["abstract_clean"]).tolist()
# Guarantee docs is an iterable of strings (no Nones)
docs = ["" if (d is None or (isinstance(d, float) and np.isnan(d))) else str(d) for d in docs]

n_docs = len(docs)
print(f"Loaded {n_docs} documents for clustering...")


# ===================== Embeddings =====================
print("Generating embeddings...")
embedder = SentenceTransformer(EMBEDDING_MODEL)

# Process in batches for memory efficiency
batch_size = 64
if n_docs > 1000:
    embeddings = []
    for i in range(0, n_docs, batch_size):
        batch = docs[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(n_docs-1)//batch_size + 1}")
        batch_emb = embedder.encode(
            batch,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        embeddings.append(batch_emb)
    embeddings = np.vstack(embeddings)
else:
    embeddings = embedder.encode(
        docs,
        show_progress_bar=True,
        batch_size=batch_size,
        normalize_embeddings=True
    )

print(f"Generated embeddings with shape: {embeddings.shape}")


# ===================== Dimensionality Reduction =====================
print("Applying UMAP dimensionality reduction...")
umap_model = UMAP(
    n_neighbors=UMAP_N_NEIGHBORS,
    n_components=UMAP_N_COMPONENTS,
    min_dist=UMAP_MIN_DIST,
    metric='cosine',
    random_state=42
)
reduced_embeddings = umap_model.fit_transform(embeddings)
print(f"Reduced embeddings to shape: {reduced_embeddings.shape}")


# ===================== BERTopic with Enhanced Components =====================
# Strong, clean vectorizer (1–2 grams, english stopwords + extras)
base_stop = CountVectorizer(stop_words="english").get_stop_words()
vectorizer = CountVectorizer(
    ngram_range=(1, 2),
    stop_words=list(set(base_stop | EXTRA_STOP)),
    max_df=0.95,
    min_df=2
)

# Enhanced clustering with HDBSCAN
hdbscan_model = HDBSCAN(
    min_cluster_size=MIN_CLUSTER_SIZE,
    metric='euclidean',
    cluster_selection_method='eom',
    prediction_data=True
)

# Find optimal number of topics using silhouette score
print("Finding optimal clustering parameters...")
best_score = -1
best_topics = None
best_model = None

for min_size in range(max(2, MIN_CLUSTER_SIZE-2), MIN_CLUSTER_SIZE+4):
    try:
        temp_hdbscan = HDBSCAN(
            min_cluster_size=min_size,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        
        temp_model = BERTopic(
            vectorizer_model=vectorizer,
            hdbscan_model=temp_hdbscan,
            calculate_probabilities=True,
            top_n_words=30,
            low_memory=True,
            verbose=False,
        )
        
        temp_topics, _ = temp_model.fit_transform(docs, reduced_embeddings)
        unique_topics = set(temp_topics)
        
        if len(unique_topics) > 1 and -1 not in unique_topics:
            score = silhouette_score(reduced_embeddings, temp_topics)
            print(f"Min cluster size {min_size}: {len(unique_topics)} topics, silhouette score: {score:.3f}")
            
            if score > best_score:
                best_score = score
                best_topics = temp_topics
                best_model = temp_model
                
    except Exception as e:
        print(f"Failed with min_size {min_size}: {e}")
        continue

# Use best model or fallback
if best_model is not None:
    topic_model = best_model
    topics = best_topics
    print(f"Selected model with silhouette score: {best_score:.3f}")
else:
    print("Using fallback model...")
    topic_model = BERTopic(
        vectorizer_model=vectorizer,
        hdbscan_model=hdbscan_model,
        calculate_probabilities=True,
        top_n_words=30,
        low_memory=True,
        verbose=False,
    )
    topics, probs = topic_model.fit_transform(docs, reduced_embeddings)

# ===================== Reassign outliers (-1) =====================
topic_ids = [t for t in sorted(topic_model.get_topics().keys()) if t != -1]
if np.any(np.array(topics) == -1) and len(topic_ids) > 0:
    print("Reassigning outliers to nearest clusters...")
    # centroids using reduced embeddings
    centroids = {}
    for tid in topic_ids:
        idx = np.where(np.array(topics) == tid)[0]
        if len(idx) == 0:
            continue
        centroids[tid] = np.mean(reduced_embeddings[idx], axis=0, dtype=np.float32)
    if centroids:
        centroid_mat = np.vstack([centroids[tid] for tid in centroids.keys()])
        centroid_keys = list(centroids.keys())

        out_idx = np.where(np.array(topics) == -1)[0]
        if len(out_idx) > 0:
            sims = cosine_similarity(reduced_embeddings[out_idx], centroid_mat)
            nearest = sims.argmax(axis=1)
            for j, i_doc in enumerate(out_idx):
                topics[i_doc] = centroid_keys[nearest[j]]
            print(f"Reassigned {len(out_idx)} outliers")

        # refresh topic term representations to reflect new assignments
        try:
            topic_model.update_topics(docs, topics=topics, vectorizer_model=vectorizer)
        except TypeError as e:
            # Some BERTopic versions require explicit string-only docs
            safe_docs = [str(x) for x in docs]
            topic_model.update_topics(safe_docs, topics=topics, vectorizer_model=vectorizer)

# ===================== Clean 5-term labels =====================
new_labels = {}
for tid in sorted(set(topics)):
    terms = topic_model.get_topic(tid) or []
    clean5 = unique_top_terms(terms, k=5)
    if not clean5:
        clean5 = [w for (w, _) in terms[:5]] or [f"topic-{tid}"]
    new_labels[tid] = " • ".join(clean5)

topic_model.set_topic_labels(new_labels)

# ===================== Reporting =====================
series = pd.Series(topics)
counts = series.value_counts().sort_index()
total = int(counts.sum())

print("\n=== ENHANCED TOPICS (BERTopic + UMAP + HDBSCAN) — 5 clean keywords + ALL paper titles ===\n")
print(f"Found {len(counts)} topics totaling {total} papers.")
if best_score > 0:
    print(f"Silhouette score: {best_score:.3f}")
print()

# If somehow -1 still exists, warn
n_out = int((series == -1).sum())
if n_out > 0:
    print(f"WARNING: {n_out} items are still outliers (-1) and won’t be counted.\n")

# Print clusters (+ NEW: non-technical summary)
df["__topic__"] = topics
for tid in sorted(counts.index):
    label = new_labels.get(tid, f"topic-{tid}")
    cluster_df = df.loc[df["__topic__"] == tid]
    avg_citation = cluster_df["citation_number"].mean()
    if avg_citation is not None and not (isinstance(avg_citation, float) and np.isnan(avg_citation)):
        avg_str = f"{int(avg_citation)}" if float(avg_citation).is_integer() else f"{avg_citation:.2f}"
    else:
        avg_str = "N/A"
    # Sort within cluster by citations desc (NaNs last)
    cluster_df_sorted = cluster_df.sort_values(by="citation_number", ascending=False, na_position="last")
    items = list(zip(cluster_df_sorted["title"].tolist(), cluster_df_sorted["citation_number"].tolist()))
    print_cluster(f"[{tid}] {label} — avg citation: {avg_str}", items)

    # ------- NEW: brief, non-technical summary per cluster -------
    kw_list = label.split(" • ") if label else []
    combined_docs = cluster_df_sorted["abstract"].tolist()  # keep original punctuation for sentence split
    summary_text = generate_cluster_summary(combined_docs, kw_list, n_sentences=2, max_chars=350, mmr_lambda=0.6)
    if summary_text:
        print(f"    Summary (non-technical): {summary_text}\n")
    else:
        print(f"    Summary (non-technical): (no concise summary available)\n")
    # -------------------------------------------------------------

# Final sanity line
if total != n_docs:
    print(f"\nNOTE: Sum of cluster sizes ({total}) != number of rows ({n_docs}). "
          f"Consider lowering MIN_CLUSTER_SIZE or checking for empty docs.")
else:
    print(f"\n✔ Sum of cluster sizes matches dataset size: {total} == {n_docs}")
