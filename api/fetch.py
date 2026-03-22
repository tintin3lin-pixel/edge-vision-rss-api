"""
Edge Vision RSS Aggregator API
Vercel Serverless Function - Python Runtime
Fetches 30 tech signal sources and returns cleaned JSON
"""
import json
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler


SOURCES = [
    # --- Global Tech Media ---
    ("https://hnrss.org/frontpage",           "Hacker News",       "developer"),
    ("https://techcrunch.com/feed/",           "TechCrunch",        "industry"),
    ("https://www.theverge.com/rss/index.xml", "The Verge",         "industry"),
    ("https://feeds.wired.com/wired/index",    "Wired",             "industry"),
    ("https://www.technologyreview.com/feed/", "MIT Tech Review",   "research"),
    ("https://venturebeat.com/feed/",          "VentureBeat",       "industry"),
    # --- AI Labs ---
    ("https://openai.com/blog/rss.xml",        "OpenAI Blog",       "lab"),
    ("https://www.anthropic.com/rss.xml",      "Anthropic Blog",    "lab"),
    ("https://deepmind.google/blog/rss.xml",   "DeepMind Blog",     "lab"),
    # --- Developer / Research ---
    ("https://huggingface.co/blog/feed.xml",   "HuggingFace Blog",  "developer"),
    ("https://export.arxiv.org/rss/cs.AI",     "arXiv AI",          "research"),
    ("https://export.arxiv.org/rss/cs.LG",     "arXiv ML",          "research"),
    ("https://paperswithcode.com/latest.rss",  "Papers with Code",  "research"),
    ("https://bair.berkeley.edu/blog/feed.xml","BAIR Blog",         "research"),
    # --- Reddit ---
    ("https://www.reddit.com/r/MachineLearning/.rss",  "Reddit ML",         "developer"),
    ("https://www.reddit.com/r/LocalLLaMA/.rss",       "Reddit LocalLLaMA", "developer"),
    ("https://www.reddit.com/r/artificial/.rss",       "Reddit AI",         "developer"),
    # --- Capital / VC ---
    ("https://a16z.com/feed/",                 "a16z Blog",         "capital"),
    ("https://www.sequoiacap.com/feed/",       "Sequoia Blog",      "capital"),
    # --- China Tech ---
    ("https://36kr.com/feed",                  "36Kr",              "china"),
    ("https://www.jiqizhixin.com/rss",         "Jiqizhixin",        "china"),
    # --- Product ---
    ("https://www.producthunt.com/feed",       "Product Hunt",      "product"),
    # --- Newsletters / Blogs ---
    ("https://stratechery.com/feed/",          "Stratechery",       "analysis"),
    ("https://www.ben-evans.com/benedictevans/rss.xml", "Benedict Evans", "analysis"),
    ("https://simonwillison.net/atom/everything/", "Simon Willison", "developer"),
    ("https://lilianweng.github.io/index.xml", "Lilian Weng Blog",  "research"),
    # --- NVIDIA / Hardware ---
    ("https://blogs.nvidia.com/feed/",         "NVIDIA Blog",       "hardware"),
    # --- Podcast / Video ---
    ("https://lexfridman.com/feed/podcast/",   "Lex Fridman",       "analysis"),
    # --- Backup China ---
    ("https://www.pingwest.com/feed",          "PingWest",          "china"),
]


def fetch_rss(url, source_name, source_dim, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EdgeVisionBot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        items = []
        item_pat   = re.compile(r"<(?:item|entry)>(.*?)</(?:item|entry)>", re.DOTALL)
        title_pat  = re.compile(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL)
        link_pat   = re.compile(r"<link[^>]*>(https?://[^\s<\"]+?)</link>", re.DOTALL)
        link_href  = re.compile(r"<link[^>]+href=[\"'](https?://[^\"'\s]+)", re.DOTALL)
        pub_pat    = re.compile(r"<(?:pubDate|published|updated)[^>]*>(.*?)</(?:pubDate|published|updated)>", re.DOTALL)

        for m in item_pat.finditer(content):
            chunk = m.group(1)
            t = title_pat.search(chunk)
            if not t:
                continue
            title = re.sub(r"<[^>]+>", "", t.group(1)).strip()
            title = re.sub(r"&amp;", "&", title)
            title = re.sub(r"&lt;", "<", title)
            title = re.sub(r"&gt;", ">", title)
            title = re.sub(r"&quot;", '"', title)
            title = re.sub(r"&#\d+;", "", title).strip()
            if not title or len(title) < 8:
                continue
            lm = link_pat.search(chunk) or link_href.search(chunk)
            link = lm.group(1).strip() if lm else ""
            pm = pub_pat.search(chunk)
            pub = pm.group(1).strip() if pm else ""
            items.append({
                "title":     title[:200],
                "link":      link,
                "pub_date":  pub,
                "source":    source_name,
                "dimension": source_dim,
            })
        return items[:15]
    except Exception:
        return []


def aggregate():
    all_items = []
    failed = []
    for url, name, dim in SOURCES:
        items = fetch_rss(url, name, dim)
        if items:
            all_items.extend(items)
        else:
            failed.append(name)
        time.sleep(0.2)

    # Dedup by title key
    seen = set()
    deduped = []
    for item in all_items:
        key = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", item["title"].lower())[:50]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    # Source stats
    src_counts = {}
    dim_counts = {}
    for item in deduped:
        src_counts[item["source"]] = src_counts.get(item["source"], 0) + 1
        dim_counts[item["dimension"]] = dim_counts.get(item["dimension"], 0) + 1

    top_sources = sorted(src_counts.items(), key=lambda x: -x[1])[:10]
    fetch_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M CST")

    return {
        "items":           deduped[:100],
        "total":           len(deduped),
        "fetch_time":      fetch_time,
        "sources_summary": ", ".join(f"{s}({c})" for s, c in top_sources),
        "dim_summary":     ", ".join(f"{d}:{c}" for d, c in sorted(dim_counts.items(), key=lambda x: -x[1])),
        "failed_sources":  failed,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = aggregate()
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
