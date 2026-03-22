"""
Edge Vision RSS Aggregator API v2.0
Vercel Serverless Function - Python Runtime

三层过滤架构：
1. 信号源层：高质量源全量保留，混杂源只保留含追踪词条目
2. 关键词层：人物/公司/技术事件三维度追踪
3. 去重层：标题指纹去重
"""
import json
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler


# ============================================================
# 三维度追踪关键词库
# ============================================================

# A. 人物维度 - 追踪具体人的言论/动向
PERSON_KEYWORDS = [
    # OpenAI
    "sam altman", "greg brockman", "ilya sutskever",
    # Nvidia
    "jensen huang", "黄仁勋",
    # Anthropic
    "dario amodei", "daniela amodei",
    # Google / DeepMind
    "demis hassabis", "sundar pichai", "jeff dean",
    # Meta
    "yann lecun", "mark zuckerberg", "zuckerberg",
    # Microsoft
    "satya nadella", "mustafa suleyman",
    # xAI / Tesla
    "elon musk",
    # Independent
    "andrej karpathy", "geoffrey hinton", "gary marcus",
    # VC / Capital
    "marc andreessen", "peter thiel", "reid hoffman",
    # China
    "李彦宏", "马化腾", "张朝阳", "任正非", "王小川",
]

# B. 公司/产品维度 - 追踪具体公司的发布/融资/政策
COMPANY_KEYWORDS = [
    # AI Labs
    "openai", "anthropic", "deepmind", "google ai", "google deepmind",
    "meta ai", "xai", "mistral", "cohere", "inflection", "stability ai",
    "hugging face", "huggingface",
    # Chips / Hardware
    "nvidia", "amd", "intel", "tsmc", "qualcomm", "apple silicon",
    "groq", "cerebras", "sambanova", "tenstorrent",
    # Cloud
    "aws", "azure", "google cloud", "cloudflare",
    # AI Apps
    "cursor", "perplexity", "midjourney", "runway", "elevenlabs",
    "character.ai", "character ai", "claude", "chatgpt", "gemini", "copilot",
    # China AI
    "deepseek", "kimi", "moonshot", "zhipu", "智谱", "月之暗面",
    "零一万物", "百川", "讯飞", "文心", "通义", "混元",
    "字节跳动", "百度", "阿里云", "华为", "商汤", "旷视",
]

# C. 技术事件维度 - 追踪范式突破/行业格局变化
TECH_EVENT_KEYWORDS = [
    # 模型能力突破
    "agi", "superintelligence", "reasoning model", "o3", "o4",
    "multimodal", "vision model", "audio model", "video generation",
    "context window", "long context", "1m token", "10m token",
    "benchmark", "surpass human", "state of the art", "sota",
    "inference speed", "latency", "tokens per second",
    # 模型架构
    "transformer", "mamba", "ssm", "mixture of experts", "moe",
    "rlhf", "dpo", "constitutional ai", "alignment",
    "rag", "retrieval", "tool use", "function calling",
    "agent", "agentic", "autonomous", "self-improving", "multi-agent",
    # 行业事件
    "acquisition", "merger", "ipo", "funding round", "series",
    "valuation", "billion", "layoff", "hiring",
    "regulation", "ban", "lawsuit", "antitrust", "eu ai act",
    "open source", "open weights", "open model", "license",
    "data breach", "safety", "jailbreak", "alignment failure",
    # 通用AI/科技
    "llm", "large language model", "foundation model",
    "generative ai", "diffusion model", "neural network",
    "machine learning", "deep learning", "fine-tuning",
    "gpu", "tpu", "ai chip", "data center", "compute",
    "robotics", "humanoid robot", "autonomous vehicle",
    "ai", "artificial intelligence",
]

# 合并所有追踪词（用于混杂来源的过滤）
ALL_TRACK_KEYWORDS = PERSON_KEYWORDS + COMPANY_KEYWORDS + TECH_EVENT_KEYWORDS


# ============================================================
# 信号源配置（按质量分级）
# ============================================================

# 高质量源：内容高度聚焦，全量保留
HIGH_QUALITY_SOURCES = [
    # AI Labs 官方博客
    ("https://openai.com/blog/rss.xml",          "OpenAI Blog",       "lab"),
    ("https://www.anthropic.com/rss.xml",         "Anthropic Blog",    "lab"),
    ("https://deepmind.google/blog/rss.xml",      "DeepMind Blog",     "lab"),
    ("https://huggingface.co/blog/feed.xml",      "HuggingFace Blog",  "developer"),
    ("https://blogs.nvidia.com/feed/",            "NVIDIA Blog",       "hardware"),
    # 研究
    ("https://export.arxiv.org/rss/cs.AI",        "arXiv AI",          "research"),
    ("https://export.arxiv.org/rss/cs.LG",        "arXiv ML",          "research"),
    ("https://export.arxiv.org/rss/cs.CL",        "arXiv NLP",         "research"),
    ("https://paperswithcode.com/latest.rss",     "Papers with Code",  "research"),
    ("https://lilianweng.github.io/index.xml",    "Lilian Weng Blog",  "research"),
    ("https://bair.berkeley.edu/blog/feed.xml",   "BAIR Blog",         "research"),
    # 开发者社区
    ("https://simonwillison.net/atom/everything/","Simon Willison",    "developer"),
    # VC / 分析
    ("https://a16z.com/feed/",                    "a16z Blog",         "capital"),
    ("https://stratechery.com/feed/",             "Stratechery",       "analysis"),
    ("https://www.ben-evans.com/benedictevans/rss.xml", "Benedict Evans", "analysis"),
    # 中国 AI 专业媒体
    ("https://www.jiqizhixin.com/rss",            "Jiqizhixin",        "china"),
]

# 混杂源：内容宽泛，只保留含追踪词的条目
MIXED_SOURCES = [
    ("https://hnrss.org/frontpage",               "Hacker News",       "developer"),
    ("https://techcrunch.com/feed/",              "TechCrunch",        "industry"),
    ("https://www.theverge.com/rss/index.xml",    "The Verge",         "industry"),
    ("https://feeds.wired.com/wired/index",       "Wired",             "industry"),
    ("https://www.technologyreview.com/feed/",    "MIT Tech Review",   "research"),
    ("https://venturebeat.com/feed/",             "VentureBeat",       "industry"),
    ("https://www.sequoiacap.com/feed/",          "Sequoia Blog",      "capital"),
    ("https://www.producthunt.com/feed",          "Product Hunt",      "product"),
    ("https://lexfridman.com/feed/podcast/",      "Lex Fridman",       "analysis"),
    ("https://36kr.com/feed",                     "36Kr",              "china"),
    ("https://www.pingwest.com/feed",             "PingWest",          "china"),
]

# Google News 专题追踪源（按人物/公司定制）
GOOGLE_NEWS_SOURCES = [
    ("https://news.google.com/rss/search?q=Jensen+Huang+AI&hl=en&gl=US&ceid=US:en",
     "GNews: Jensen Huang", "person_track"),
    ("https://news.google.com/rss/search?q=Sam+Altman+OpenAI&hl=en&gl=US&ceid=US:en",
     "GNews: Sam Altman", "person_track"),
    ("https://news.google.com/rss/search?q=Elon+Musk+xAI+Grok&hl=en&gl=US&ceid=US:en",
     "GNews: Elon Musk xAI", "person_track"),
    ("https://news.google.com/rss/search?q=Anthropic+Claude+AI&hl=en&gl=US&ceid=US:en",
     "GNews: Anthropic", "company_track"),
    ("https://news.google.com/rss/search?q=Nvidia+GPU+AI+chip&hl=en&gl=US&ceid=US:en",
     "GNews: Nvidia", "company_track"),
    ("https://news.google.com/rss/search?q=AI+regulation+policy+2026&hl=en&gl=US&ceid=US:en",
     "GNews: AI Policy", "policy_track"),
    ("https://news.google.com/rss/search?q=AI+funding+startup+2026&hl=en&gl=US&ceid=US:en",
     "GNews: AI Funding", "capital_track"),
    ("https://news.google.com/rss/search?q=DeepSeek+Kimi+Chinese+AI&hl=en&gl=US&ceid=US:en",
     "GNews: China AI", "china_track"),
]

# Reddit 社区（开发者第一手讨论）
REDDIT_SOURCES = [
    ("https://www.reddit.com/r/MachineLearning/.rss",  "Reddit ML",         "developer"),
    ("https://www.reddit.com/r/LocalLLaMA/.rss",       "Reddit LocalLLaMA", "developer"),
    ("https://www.reddit.com/r/artificial/.rss",       "Reddit AI",         "developer"),
    ("https://www.reddit.com/r/singularity/.rss",      "Reddit Singularity","developer"),
]


# ============================================================
# 核心函数
# ============================================================

def fetch_rss(url, source_name, source_dim, timeout=12):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EdgeVisionBot/2.0)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        items = []
        item_pat  = re.compile(r"<(?:item|entry)>(.*?)</(?:item|entry)>", re.DOTALL)
        title_pat = re.compile(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL)
        link_pat  = re.compile(r"<link[^>]*>(https?://[^\s<\"]+?)</link>", re.DOTALL)
        link_href = re.compile(r"<link[^>]+href=[\"'](https?://[^\"'\s]+)", re.DOTALL)
        pub_pat   = re.compile(r"<(?:pubDate|published|updated)[^>]*>(.*?)</(?:pubDate|published|updated)>", re.DOTALL)

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


def contains_track_keyword(title):
    """检查标题是否包含追踪关键词（三维度任一）"""
    title_lower = title.lower()
    return any(kw in title_lower for kw in ALL_TRACK_KEYWORDS)


def get_match_dimensions(title):
    """返回命中的维度标签，用于 LLM 参考"""
    title_lower = title.lower()
    dims = []
    if any(kw in title_lower for kw in PERSON_KEYWORDS):
        dims.append("person")
    if any(kw in title_lower for kw in COMPANY_KEYWORDS):
        dims.append("company")
    if any(kw in title_lower for kw in TECH_EVENT_KEYWORDS):
        dims.append("tech_event")
    return dims


def aggregate():
    all_items = []
    failed = []

    # 1. 高质量源：全量抓取
    for url, name, dim in HIGH_QUALITY_SOURCES:
        items = fetch_rss(url, name, dim)
        if items:
            all_items.extend(items)
        else:
            failed.append(name)
        time.sleep(0.15)

    # 2. 混杂源：只保留含追踪词的条目
    for url, name, dim in MIXED_SOURCES:
        items = fetch_rss(url, name, dim)
        filtered = [i for i in items if contains_track_keyword(i["title"])]
        if filtered:
            all_items.extend(filtered)
        elif not items:
            failed.append(name)
        time.sleep(0.15)

    # 3. Google News 专题追踪源：全量保留
    for url, name, dim in GOOGLE_NEWS_SOURCES:
        items = fetch_rss(url, name, dim)
        if items:
            all_items.extend(items)
        else:
            failed.append(name)
        time.sleep(0.2)

    # 4. Reddit 社区：只保留含追踪词的条目
    for url, name, dim in REDDIT_SOURCES:
        items = fetch_rss(url, name, dim)
        filtered = [i for i in items if contains_track_keyword(i["title"])]
        if filtered:
            all_items.extend(filtered)
        time.sleep(0.2)

    # 5. 去重（标题指纹）
    seen = set()
    deduped = []
    for item in all_items:
        key = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", item["title"].lower())[:50]
        if key not in seen:
            seen.add(key)
            # 标注命中维度，供 LLM 参考
            dims = get_match_dimensions(item["title"])
            item["track_dims"] = dims
            deduped.append(item)

    # 6. 统计
    src_counts = {}
    dim_counts = {}
    for item in deduped:
        src_counts[item["source"]] = src_counts.get(item["source"], 0) + 1
        dim_counts[item["dimension"]] = dim_counts.get(item["dimension"], 0) + 1

    top_sources = sorted(src_counts.items(), key=lambda x: -x[1])[:12]
    fetch_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M CST")

    return {
        "items":           deduped,
        "total":           len(deduped),
        "fetch_time":      fetch_time,
        "sources_summary": ", ".join(f"{s}({c})" for s, c in top_sources),
        "dim_summary":     ", ".join(f"{d}:{c}" for d, c in sorted(dim_counts.items(), key=lambda x: -x[1])),
        "failed_sources":  failed,
        "track_stats": {
            "person_hits":  sum(1 for i in deduped if "person" in i.get("track_dims", [])),
            "company_hits": sum(1 for i in deduped if "company" in i.get("track_dims", [])),
            "tech_hits":    sum(1 for i in deduped if "tech_event" in i.get("track_dims", [])),
        }
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
