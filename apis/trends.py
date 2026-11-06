"""
Trend Radar — what the internet is curious about right now.
All sources are keyless.

  google      Google Trends daily RSS (search spikes)
  wikipedia   Wikipedia most-read articles (yesterday)
  hackernews  Hacker News front page (tech)
  spaceflight Spaceflight News API (space & science)
  arxiv       Newest arXiv papers in the channel's fields
"""
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import config
from apis.http import get, get_json, ttl_cache

_HT = {"ht": "https://trends.google.com/trending/rss"}
_ATOM = {"a": "http://www.w3.org/2005/Atom"}

# Wikipedia's most-read list is dominated by these — never video material
_WIKI_SKIP = ("Main_Page", "Special:", "Wikipedia:", "Portal:", "File:", "Deaths_in_")


def google_trends(geo: str = "US", limit: int = 12) -> list:
    r = get("https://trends.google.com/trending/rss", params={"geo": geo})
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        news = item.find("ht:news_item", _HT)
        url = (news.findtext("ht:news_item_url", namespaces=_HT)
               if news is not None else None)
        headline = (news.findtext("ht:news_item_title", namespaces=_HT)
                    if news is not None else "")
        out.append({
            "title":  title,
            "detail": headline or "",
            "meta":   (item.findtext("ht:approx_traffic", namespaces=_HT) or "").strip(),
            "url":    url or f"https://www.google.com/search?q={quote_plus(title)}",
        })
    return out[:limit]


def wikipedia_most_read(limit: int = 12) -> list:
    day = datetime.now(timezone.utc) - timedelta(days=1)
    d = get_json(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{day:%Y/%m/%d}")
    out = []
    for a in d.get("mostread", {}).get("articles", []):
        if a.get("title", "").startswith(_WIKI_SKIP):
            continue
        out.append({
            "title":  a.get("normalizedtitle") or a.get("title", "").replace("_", " "),
            "detail": a.get("description", ""),
            "meta":   f"{a.get('views', 0):,} views",
            "url":    a.get("content_urls", {}).get("desktop", {}).get("page", ""),
        })
    return out[:limit]


def hackernews(limit: int = 10) -> list:
    d = get_json("https://hn.algolia.com/api/v1/search",
                 params={"tags": "front_page", "hitsPerPage": limit})
    return [{
        "title":  h.get("title", ""),
        "detail": h.get("author", ""),
        "meta":   f"{h.get('points', 0)} pts",
        "url":    h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
    } for h in d.get("hits", []) if h.get("title")]


def spaceflight_news(limit: int = 10) -> list:
    d = get_json("https://api.spaceflightnewsapi.net/v4/articles/",
                 params={"limit": limit})
    return [{
        "title":  a.get("title", ""),
        "detail": (a.get("summary") or "")[:160],
        "meta":   a.get("news_site", ""),
        "url":    a.get("url", ""),
    } for a in d.get("results", [])]


def arxiv_latest(limit: int = 8) -> list:
    cats = getattr(config, "ARXIV_CATEGORIES",
                   ["astro-ph.CO", "gr-qc", "quant-ph", "cs.AI", "q-bio.NC"])
    query = " OR ".join(f"cat:{c}" for c in cats)
    r = get("https://export.arxiv.org/api/query", params={
        "search_query": query, "sortBy": "submittedDate",
        "sortOrder": "descending", "max_results": limit,
    }, timeout=20)
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("a:entry", _ATOM):
        title = " ".join((e.findtext("a:title", namespaces=_ATOM) or "").split())
        cat = e.find("{http://arxiv.org/schemas/atom}primary_category")
        out.append({
            "title":  title,
            "detail": " ".join((e.findtext("a:summary", namespaces=_ATOM) or "").split())[:160],
            "meta":   cat.get("term") if cat is not None else "arXiv",
            "url":    e.findtext("a:id", namespaces=_ATOM) or "",
        })
    return out


SOURCES = {
    "google":      ("Google Trends",   google_trends),
    "wikipedia":   ("Wikipedia",       wikipedia_most_read),
    "hackernews":  ("Hacker News",     hackernews),
    "spaceflight": ("Spaceflight News", spaceflight_news),
    "arxiv":       ("arXiv",           arxiv_latest),
}


def _safe(key: str):
    label, fn = SOURCES[key]
    t0 = time.time()
    try:
        if key == "google":
            items = fn(getattr(config, "TRENDS_GEO", "US"))
        else:
            items = fn()
        return key, {"label": label, "ok": True, "items": items,
                     "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return key, {"label": label, "ok": False, "items": [],
                     "error": str(e)[:200], "ms": int((time.time() - t0) * 1000)}


@ttl_cache(15 * 60)
def get_trends() -> dict:
    """All sources, fetched in parallel, cached 15 minutes."""
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        results = dict(ex.map(_safe, SOURCES))
    return {"sources": results, "fetched_at": int(time.time())}


NICHE_KEYWORDS = {
    "tech": ["tech", "ai", "software", "code", "coding", "developer", "hardware", "chip", "semiconductor", "cyber", "robot", "cloud", "model", "algorithm", "llm", "apple", "google", "microsoft", "nvidia", "meta", "openai", "linux", "programming", "computer", "app", "web", "digital", "hack"],
    "science": ["science", "physics", "quantum", "space", "astronomy", "biology", "chemistry", "research", "paper", "lab", "study", "planet", "star", "galaxy", "telescope", "nasa", "spacex", "orbit", "rocket", "dna", "gene", "particle", "gravity", "evolution", "phase"],
    "space": ["space", "astronomy", "nasa", "spacex", "rocket", "orbit", "planet", "mars", "moon", "star", "galaxy", "telescope", "cosmic", "satellite", "astronaut", "universe", "iss", "launch", "flight"],
    "finance": ["finance", "money", "invest", "stock", "market", "economy", "economic", "crypto", "bitcoin", "ethereum", "trading", "inflation", "fed", "rate", "dollar", "bank", "banking", "wealth", "fund", "revenue", "profit", "capital", "fintech", "startup", "valuation", "spend", "budget", "debt"],
    "psychology": ["psychology", "psychological", "mind", "brain", "behavior", "mental", "cognitive", "bias", "decision", "emotion", "memory", "habit", "subconscious"],
    "crypto": ["crypto", "bitcoin", "ethereum", "blockchain", "token", "web3", "defi", "wallet", "nft", "coinbase", "binance", "mining"],
    "history": ["history", "historic", "historical", "ancient", "war", "battle", "century", "empire", "king", "queen", "dynasty", "civilization", "archaeology", "medieval", "past", "rebellion", "monarch", "wwii", "wwi", "roman", "egypt"],
    "health": ["health", "fitness", "medical", "medicine", "doctor", "hospital", "disease", "virus", "vaccine", "diet", "nutrition", "workout", "exercise", "brain", "mental", "cure", "therapy", "wellness", "muscle", "cardio", "sleep"],
    "gaming": ["game", "gaming", "playstation", "xbox", "nintendo", "steam", "gamer", "rpg", "multiplayer", "esports", "console", "gameplay", "trailer"],
}


def _word_match(word: str, text: str) -> bool:
    return bool(re.search(r"\b" + re.escape(word) + r"s?\b", text))


def matches_niche(item: dict, niche: str) -> bool:
    """Return True if a trend item matches the given niche."""
    if not niche or niche.strip().lower() in ("all", "general", "general (no niche)"):
        return True
    n = niche.strip().lower()
    title = (item.get("title") or "").lower()
    detail = (item.get("detail") or "").lower()
    src = (item.get("k") or item.get("source") or "").lower()
    text = f"{title} {detail}"

    if n in text:
        return True

    if src == "spaceflight" and any(k in n for k in ("space", "astro", "flight", "universe")):
        return True
    if src == "hackernews" and any(k in n for k in ("tech", "software", "code", "programming", "developer", "startup", "computer")):
        return True
    if src == "arxiv" and any(k in n for k in ("science", "physics", "math", "academic", "research", "paper", "quantum")):
        return True

    for cat, kws in NICHE_KEYWORDS.items():
        if cat in n:
            for kw in kws:
                if _word_match(kw, text):
                    return True

    tokens = [t for t in re.findall(r"[a-z0-9]+", n) if len(t) > 2 and t not in ("and", "the", "for", "with", "from", "about")]
    for token in tokens:
        for cat, kws in NICHE_KEYWORDS.items():
            if token == cat or token in cat:
                for kw in kws:
                    if _word_match(kw, text):
                        return True
        if _word_match(token, text):
            return True

    return False


def filter_trends_by_niche(sources: dict, niche: str) -> list[dict]:
    """Filter trend items across all sources matching a niche."""
    if not niche or niche.strip().lower() in ("all", "general", "general (no niche)"):
        items = []
        for key in ("spaceflight", "arxiv", "hackernews", "wikipedia", "google"):
            items.extend([{**it, "k": key} for it in sources.get(key, {}).get("items", [])])
        return items

    matched = []
    for key in ("spaceflight", "arxiv", "hackernews", "wikipedia", "google"):
        for it in sources.get(key, {}).get("items", []):
            item_with_key = {**it, "k": key}
            if matches_niche(item_with_key, niche):
                matched.append(item_with_key)
    return matched


def headlines(limit: int = 25, niche: str = "") -> list:
    """Flat list of trending titles — fed to the researcher for trend-aware picks."""
    data = get_trends()["sources"]
    all_items = []
    for key in ("spaceflight", "arxiv", "hackernews", "wikipedia", "google"):
        for it in data.get(key, {}).get("items", [])[:10]:
            all_items.append({**it, "k": key})

    if niche and niche.strip().lower() not in ("all", "general", "general (no niche)"):
        matched = [i["title"] for i in all_items if matches_niche(i, niche)]
        if matched:
            return matched[:limit]

    return [i["title"] for i in all_items][:limit]
