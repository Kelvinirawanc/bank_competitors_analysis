"""BANKING & FINTECH COMPETITOR INTELLIGENCE — GOOGLE PLAY ONLY

Refreshes Google Play store-level metrics and collects public written user reviews
for the fixed competitor catalog in data/apps_catalog.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from google_play_scraper import Sort, app as gp_app, reviews as gp_reviews, search as gp_search
except Exception:
    Sort = None
    gp_app = None
    gp_reviews = None
    gp_search = None

from text_analysis import classify_issue, classify_sentiment, classify_topic, validate_review

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "apps_catalog.json"
REGISTRY_PATH = DATA_DIR / "app_registry.json"
REVIEWS_PATH = DATA_DIR / "reviews.json"
SUMMARY_PATH = DATA_DIR / "summary.json"
CSV_PATH = DATA_DIR / "reviews.csv"
DIAGNOSTICS_PATH = DATA_DIR / "collection_diagnostics.json"
HISTORY_PATH = DATA_DIR / "store_history.json"

TIMEOUT = 35
SLEEP_MIN = 0.25
SLEEP_MAX = 0.65
GOOGLE_MAX_SAFE_CALLS = 250
HISTORY_MAX_SNAPSHOTS_PER_APP = 180

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

GOOGLE_SORT_MAP = {
    "NEWEST": "NEWEST",
    "RATING": "RATING",
    "HELPFUL": "HELPFUL",
}

# Live-known package IDs used only as discovery accelerators.
# Every ID is still validated against the app's expected title/developer.
KNOWN_GOOGLE_IDS: Dict[str, str] = {
    "allo_bank": "com.alloapp.yump",
    "bank_jago": "com.jago.digitalBanking",
    "seabank": "id.co.bankbkemobile.digitalbank",
    "blu_bca": "com.bcadigital.blu",
    "neobank": "com.bnc.finance",
    "bank_aladin": "id.aladinbank.mobile",
    "superbank": "id.co.bankfama.android",
    "krom_bank": "com.krom.android",
    "hibank": "com.hibank.mobile",
    "bank_raya": "id.co.bankraya.apps",
    "motionbank": "com.mnc.mbanking",
    "mybca": "com.bca.mybca.omni.android",
    "bca_mobile": "com.bca",
    "livin_mandiri": "id.bmri.livin",
    "brimo": "id.co.bri.brimo",
    "wondr_bni": "id.bni.wondr",
    "octo_mobile": "id.co.cimbniaga.mobile.android",
    "permatabank": "net.myinfosys.PermataMobileX",
    "dbank_pro": "com.dbank.mobile",
    "ocbc_mobile": "com.ocbcnisp.onemobileapp",
    "gopay": "com.gojek.gopay",
    "ovo": "ovo.id",
    "dana": "id.dana",
    "shopeepay": "com.shopee.id",
    "linkaja": "com.telkom.mwallet",
}



def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def sleep_brief() -> None:
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))


def load_json(path: Path, fallback: Any) -> Any:
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, obj: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def save_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def host(url: str) -> str:
    return urlparse(url).netloc.lower()


def same_google_domain(url: str) -> bool:
    h = host(url)
    return h.endswith("play.google.com")


def candidate_score(target: Dict[str, Any], title: str, developer: str = "") -> int:
    title_n = norm(title)
    dev_n = norm(developer)
    expected = norm(target.get("app_name", ""))
    tokens = set(expected.split())
    required = [norm(x) for x in target.get("required_terms", [])]

    score = 0
    if title_n == expected:
        score += 100
    if expected and expected in title_n:
        score += 50
    score += 8 * len(tokens.intersection(set(title_n.split())))
    score += 6 * len(set(required).intersection(set(title_n.split())))
    score += 5 * len(set(required).intersection(set(dev_n.split())))

    search_term = norm(target.get("search_term", ""))
    if search_term:
        score += 2 * len(set(search_term.split()).intersection(set(title_n.split())))
    return score


def validate_gp_match(target: Dict[str, Any], package_id: str, metadata: Dict[str, Any]) -> Tuple[bool, int, str]:
    title = metadata.get("title") or ""
    developer = metadata.get("developer") or ""
    score = candidate_score(target, title, developer)
    title_n = norm(title)
    expected = norm(target.get("app_name", ""))
    required = [norm(x) for x in target.get("required_terms", [])]
    title_hits = sum(1 for x in required if x and x in title_n)

    # Exact / near-exact title is preferred. For generic names, require at least
    # some expected keyword evidence from title or developer.
    good_title = title_n == expected or (expected and expected in title_n) or title_hits >= 1
    good_score = score >= 20
    if not good_title or not good_score:
        return False, score, f"low_confidence_match:title={title!r};developer={developer!r};score={score}"
    return True, score, "validated"


def google_search_html(session: requests.Session, target: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = "https://play.google.com/store/search"
    params = {"q": target.get("search_term") or target.get("app_name"), "c": "apps", "hl": "id", "gl": "ID"}
    try:
        resp = session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if "/store/apps/details" not in href:
                continue
            full = urljoin(url, href)
            q = re.search(r"[?&]id=([^&]+)", full)
            if not q:
                continue
            package_id = q.group(1)
            if package_id in seen:
                continue
            seen.add(package_id)
            title = a.get_text(" ", strip=True)
            out.append({"app_id": package_id, "title": title, "developer": "", "url": full, "source": "html_search"})
        return out
    except Exception:
        return []


def discover_google(target: Dict[str, Any], session: requests.Session) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "status": "failed",
        "method": None,
        "candidate_count": 0,
        "selected": None,
        "score": 0,
        "reason": "",
    }

    # 1) Known accelerator.
    if target.get("app_key") in KNOWN_GOOGLE_IDS:
        pid = KNOWN_GOOGLE_IDS[target["app_key"]]
        meta = fetch_google_metadata(session, pid)
        valid, score, reason = validate_gp_match(target, pid, meta)
        if valid:
            diagnostics.update({"status":"validated","method":"known_id","selected":pid,"score":score,"reason":reason})
            return {"app_id": pid, "url": f"https://play.google.com/store/apps/details?id={pid}&hl=id&gl=ID", "metadata": meta, "diagnostics": diagnostics}
        diagnostics["known_id_validation"] = {"id": pid, "score": score, "reason": reason, "metadata": meta}

    candidates: List[Dict[str, Any]] = []

    # 2) google-play-scraper search.
    if gp_search is not None:
        for lang in ("id", "en"):
            try:
                rows = gp_search(target.get("search_term") or target.get("app_name"), lang=lang, country="id", n_hits=20)
                for row in rows:
                    candidates.append({
                        "app_id": row.get("appId"),
                        "title": row.get("title") or "",
                        "developer": row.get("developer") or "",
                        "url": row.get("url") or "",
                        "source": f"package_search:{lang}",
                    })
            except Exception:
                pass
            sleep_brief()

    # 3) Direct Google Play search-page fallback.
    candidates.extend(google_search_html(session, target))

    # Remove duplicates.
    unique: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        if c.get("app_id"):
            unique[str(c["app_id"])] = c

    diagnostics["candidate_count"] = len(unique)
    if not unique:
        diagnostics["reason"] = "no_candidates"
        return {"app_id": None, "url": None, "metadata": {}, "diagnostics": diagnostics}

    ranked = sorted(unique.values(), key=lambda c: candidate_score(target, c.get("title", ""), c.get("developer", "")), reverse=True)

    for cand in ranked[:12]:
        pid = str(cand["app_id"])
        meta = fetch_google_metadata(session, pid)
        valid, score, reason = validate_gp_match(target, pid, meta)
        if valid:
            url = meta.get("url") or cand.get("url") or f"https://play.google.com/store/apps/details?id={pid}&hl=id&gl=ID"
            diagnostics.update({"status":"validated","method":cand.get("source"),"selected":pid,"score":score,"reason":reason})
            return {"app_id": pid, "url": url, "metadata": meta, "diagnostics": diagnostics}
        sleep_brief()

    diagnostics["reason"] = "all_candidates_failed_validation"
    return {"app_id": None, "url": None, "metadata": {}, "diagnostics": diagnostics}


def fetch_google_metadata(session: requests.Session, package_id: str) -> Dict[str, Any]:
    if gp_app is None:
        return fetch_google_metadata_http(session, package_id)
    try:
        m = gp_app(package_id, lang="id", country="id")
        return {
            "title": m.get("title"),
            "developer": m.get("developer"),
            "score": m.get("score"),
            "ratings": m.get("ratings"),
            "reviews": m.get("reviews"),
            "installs": m.get("installs"),
            "updated": m.get("updated"),
            "url": m.get("url") or f"https://play.google.com/store/apps/details?id={package_id}&hl=id&gl=ID",
        }
    except Exception:
        return fetch_google_metadata_http(session, package_id)


def fetch_google_metadata_http(session: requests.Session, package_id: str) -> Dict[str, Any]:
    url = f"https://play.google.com/store/apps/details?id={package_id}&hl=id&gl=ID"
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.find("h1")
        developer = None
        # Search anchors around developer page / author links.
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if "developer" in href.lower() and a.get_text(strip=True):
                developer = a.get_text(" ", strip=True)
                break
        return {
            "title": title.get_text(" ", strip=True) if title else package_id,
            "developer": developer or "",
            "score": None,
            "ratings": None,
            "reviews": None,
            "installs": None,
            "updated": None,
            "url": url,
        }
    except Exception:
        return {"title": package_id, "developer": "", "url": url}


def normalize_gp_review(item: Dict[str, Any], app_rec: Dict[str, Any], lang: str, sort_name: str) -> Optional[Dict[str, Any]]:
    review_id = str(item.get("reviewId") or "").strip()
    if not review_id:
        return None
    dt = item.get("at")
    return {
        "review_id": f"gp:{review_id}",
        "source_review_id": review_id,
        "app_key": app_rec["app_key"],
        "app_name": app_rec["app_name"],
        "company": app_rec["company"],
        "industry": app_rec["industry"],
        "role": app_rec["role"],
        "platform": "Google Play",
        "store_country": "id",
        "rating": int(item.get("score") or 0),
        "review_title": "",
        "review_text": item.get("content") or "",
        "review_date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt or ""),
        "app_version": item.get("reviewCreatedVersion") or "",
        "user_name": item.get("userName") or "",
        "thumbs_up": int(item.get("thumbsUpCount") or 0),
        "developer_reply": item.get("replyContent") or "",
        "source_url": app_rec.get("google_play_url") or "",
        "collection_language": lang,
        "collection_sort": sort_name,
        "scraped_at": now_iso(),
        "is_demo": False,
    }


def collect_google_stream(
    app_rec: Dict[str, Any],
    lang: str,
    sort_name: str,
    max_reviews: int,
    diagnostics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if gp_reviews is None or not app_rec.get("google_play_id"):
        diagnostics.update({"status":"skipped","reason":"google_play_scraper_not_available_or_no_id"})
        return []

    sort_value = getattr(Sort, GOOGLE_SORT_MAP.get(sort_name, "NEWEST"), None)
    if sort_value is None:
        diagnostics.update({"status":"skipped","reason":f"sort_not_supported:{sort_name}"})
        return []

    token = None
    rows: List[Dict[str, Any]] = []
    calls = 0
    empty_pages = 0
    last_token = None

    while calls < GOOGLE_MAX_SAFE_CALLS:
        if max_reviews > 0 and len(rows) >= max_reviews:
            diagnostics.update({"termination":"max_reviews_reached"})
            break

        calls += 1
        count = 200
        if max_reviews > 0:
            count = min(count, max_reviews - len(rows))

        kwargs = {"lang": lang, "country": "id", "sort": sort_value, "count": count}
        if token is not None:
            kwargs["continuation_token"] = token

        try:
            batch, new_token = gp_reviews(app_rec["google_play_id"], **kwargs)
        except TypeError:
            try:
                if token is None:
                    batch, new_token = gp_reviews(app_rec["google_play_id"], lang=lang, country="id", sort=sort_value, count=count)
                else:
                    batch, new_token = gp_reviews(app_rec["google_play_id"], lang=lang, country="id", sort=sort_value, count=count, continuation_token=token)
            except Exception as exc:
                diagnostics.update({"status":"failed","error":str(exc),"termination":"exception"})
                break
        except Exception as exc:
            diagnostics.update({"status":"failed","error":str(exc),"termination":"exception"})
            break

        if not batch:
            empty_pages += 1
            diagnostics["empty_pages"] = empty_pages
            if new_token and new_token != token:
                token = new_token
                continue
            diagnostics["termination"] = "empty_batch_without_new_token"
            break

        empty_pages = 0
        for item in batch:
            row = normalize_gp_review(item, app_rec, lang, sort_name)
            if row:
                rows.append(row)

        if not new_token or new_token == token or new_token == last_token:
            diagnostics["termination"] = "no_new_continuation_token"
            break

        last_token = token
        token = new_token
        sleep_brief()

    diagnostics.update({
        "status": "ok" if rows else diagnostics.get("status", "ok"),
        "calls": calls,
        "raw_reviews": len(rows),
        "unique_review_ids": len({r["review_id"] for r in rows}),
    })
    return rows


def enrich_review(review: Dict[str, Any]) -> Dict[str, Any]:
    rating = int(review.get("rating") or 0)
    sentiment, s_conf = classify_sentiment(review.get("review_text", ""), rating)
    topic, t_conf = classify_topic(review.get("review_text", ""))
    issue = classify_issue(review.get("review_text", ""))
    validation = validate_review(review)
    out = dict(review)
    out.update({
        "sentiment": sentiment,
        "sentiment_confidence": s_conf,
        "topic": topic,
        "topic_confidence": t_conf,
        "primary_issue": issue,
        **validation,
        "is_demo": False,
    })
    return out


def aggregate(reviews: List[Dict[str, Any]], registry: List[Dict[str, Any]]) -> Dict[str, Any]:
    def pct(n: int, d: int) -> float:
        return round(n / d * 100, 1) if d else 0.0

    by_app: Dict[str, List[Dict[str, Any]]] = {}
    by_industry: Dict[str, List[Dict[str, Any]]] = {}
    by_month: Dict[str, List[Dict[str, Any]]] = {}
    topics: Dict[str, int] = {}
    issues: Dict[str, int] = {}
    for r in reviews:
        by_app.setdefault(r['app_key'], []).append(r)
        by_industry.setdefault(r['industry'], []).append(r)
        month = str(r.get('review_date', ''))[:7]
        if month:
            by_month.setdefault(month, []).append(r)
        topic = r.get('topic', 'General')
        topics[topic] = topics.get(topic, 0) + 1
        if r.get('sentiment') == 'Negative':
            issue = r.get('primary_issue', 'General')
            issues[issue] = issues.get(issue, 0) + 1

    def review_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(rows)
        vals = [int(r.get('rating')) for r in rows if str(r.get('rating', '')).isdigit() and 1 <= int(r.get('rating')) <= 5]
        return {
            'review_count': n,
            'avg_rating_from_reviews': round(sum(vals) / len(vals), 2) if vals else None,
            'positive_pct': pct(sum(r.get('sentiment') == 'Positive' for r in rows), n),
            'neutral_pct': pct(sum(r.get('sentiment') == 'Neutral' for r in rows), n),
            'negative_pct': pct(sum(r.get('sentiment') == 'Negative' for r in rows), n),
            'one_star_pct': pct(sum(r.get('rating') == 1 for r in rows), n),
            'two_star_pct': pct(sum(r.get('rating') == 2 for r in rows), n),
            'three_star_pct': pct(sum(r.get('rating') == 3 for r in rows), n),
            'four_star_pct': pct(sum(r.get('rating') == 4 for r in rows), n),
            'five_star_pct': pct(sum(r.get('rating') == 5 for r in rows), n),
            'actionable_review_pct': pct(sum(bool(r.get('actionable')) for r in rows), n),
        }

    apps = []
    for rec in registry:
        rows = by_app.get(rec['app_key'], [])
        meta = rec.get('google_play_metadata') or {}
        apps.append({
            'app_key': rec['app_key'],
            'app_name': rec['app_name'],
            'company': rec['company'],
            'industry': rec['industry'],
            'role': rec['role'],
            'google_play_id': rec.get('google_play_id'),
            'google_play_url': rec.get('google_play_url'),
            'store_rating': meta.get('score'),
            'store_ratings': meta.get('ratings'),
            'store_reviews': meta.get('reviews'),
            'installs': meta.get('installs'),
            'store_updated': meta.get('updated'),
            **review_summary(rows),
        })

    digital = [a for a in apps if a['industry'] == 'Digital Banks' and isinstance(a.get('store_rating'), (int, float))]
    digital.sort(key=lambda x: x['store_rating'], reverse=True)
    allo_rank = next((i + 1 for i, a in enumerate(digital) if a['app_key'] == 'allo_bank'), None)

    sentiment = []
    for industry, rows in sorted(by_industry.items()):
        sentiment.append({
            'industry': industry,
            'positive': sum(r.get('sentiment') == 'Positive' for r in rows),
            'neutral': sum(r.get('sentiment') == 'Neutral' for r in rows),
            'negative': sum(r.get('sentiment') == 'Negative' for r in rows),
        })

    trend = []
    for month, rows in sorted(by_month.items()):
        vals = [int(r.get('rating')) for r in rows if str(r.get('rating', '')).isdigit()]
        trend.append({
            'month': month,
            'review_count': len(rows),
            'avg_rating': round(sum(vals) / len(vals), 2) if vals else None,
            'negative_count': sum(r.get('sentiment') == 'Negative' for r in rows),
        })

    return {
        'generated_at': now_iso(),
        'source': 'Google Play',
        'is_demo': False,
        'overall': review_summary(reviews),
        'digital_bank_allo_rank': allo_rank,
        'apps': apps,
        'industry_summary': [{'industry': k, **review_summary(v)} for k, v in sorted(by_industry.items())],
        'sentiment_by_industry': sentiment,
        'topic_summary': [{'topic': k, 'count': v} for k, v in sorted(topics.items(), key=lambda x: (-x[1], x[0]))],
        'top_negative_issues': [{'issue': k, 'count': v} for k, v in sorted(issues.items(), key=lambda x: (-x[1], x[0]))],
        'trend': trend,
    }


def build_registry(catalog: List[Dict[str, Any]], existing: Dict[str, Any], session: requests.Session, skip_discovery: bool, only: Optional[set[str]] = None) -> List[Dict[str, Any]]:
    old = {x.get('app_key'): x for x in existing.get('apps', []) if x.get('app_key')}
    result = []
    for target in catalog:
        if only and target['app_key'] not in only:
            continue
        rec = dict(target)
        old_rec = old.get(target['app_key'], {})
        if skip_discovery and old_rec.get('google_play_id'):
            rec.update({k: old_rec[k] for k in ('google_play_id','google_play_url','google_play_metadata','google_play_discovery') if k in old_rec})
        else:
            gp = discover_google(target, session)
            if gp.get('app_id'):
                rec['google_play_id'] = gp['app_id']
                rec['google_play_url'] = gp.get('url') or rec.get('google_play_url')
                rec['google_play_metadata'] = gp.get('metadata', {})
                rec['google_play_discovery'] = gp.get('diagnostics', {})
            else:
                rec['google_play_id'] = None
                rec['google_play_discovery'] = gp.get('diagnostics', {})
        result.append(rec)
    return result


def parse_csv_arg(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def update_store_history(registry: List[Dict[str, Any]]) -> None:
    history = load_json(HISTORY_PATH, {'generated_at': None, 'source': 'Google Play', 'snapshots': []})
    stamp = now_iso()
    rows = []
    for rec in registry:
        meta = rec.get('google_play_metadata') or {}
        if meta.get('score') is None and meta.get('ratings') is None and meta.get('reviews') is None:
            continue
        rows.append({
            'snapshot_at': stamp,
            'app_key': rec['app_key'],
            'app_name': rec['app_name'],
            'industry': rec['industry'],
            'store_rating': meta.get('score'),
            'store_ratings': meta.get('ratings'),
            'store_reviews': meta.get('reviews'),
            'installs': meta.get('installs'),
        })
    history['generated_at'] = stamp
    history['snapshots'] = history.get('snapshots', []) + rows
    counts: Dict[str, int] = {}
    trimmed = []
    for row in reversed(history['snapshots']):
        k = row.get('app_key')
        counts[k] = counts.get(k, 0) + 1
        if counts[k] <= HISTORY_MAX_SNAPSHOTS_PER_APP:
            trimmed.append(row)
    history['snapshots'] = list(reversed(trimmed))
    save_json(HISTORY_PATH, history)


def main() -> None:
    p = argparse.ArgumentParser(description='Collect Google Play store metrics and written reviews.')
    p.add_argument('--max-reviews-per-stream', type=int, default=200, help='0=continue until pagination ends; positive value caps each language/sort stream')
    p.add_argument('--google-languages', default='id,en')
    p.add_argument('--google-sorts', default='NEWEST,RATING,HELPFUL')
    p.add_argument('--fresh', action='store_true', help='start from zero instead of merging existing reviews')
    p.add_argument('--skip-discovery', action='store_true', help='reuse validated IDs from app_registry.json')
    p.add_argument('--only-app', default='')
    args = p.parse_args()

    if gp_reviews is None:
        raise RuntimeError('google-play-scraper is not installed. Run: python -m pip install -r requirements.txt')

    session = requests.Session(); session.headers.update(HEADERS)
    catalog = load_json(CATALOG_PATH, {'apps': []}).get('apps', [])
    previous_registry = load_json(REGISTRY_PATH, {'apps': []})
    previous_reviews = [] if args.fresh else load_json(REVIEWS_PATH, {'reviews': []}).get('reviews', [])
    previous_reviews = [r for r in previous_reviews if r.get('platform') == 'Google Play']
    stored = {r.get('review_id'): r for r in previous_reviews if r.get('review_id')}
    only = set(parse_csv_arg(args.only_app)) or None

    registry = build_registry(catalog, previous_registry, session, args.skip_discovery, only)
    # Refresh store-level metadata on every run — this is what makes the project a tracker.
    for rec in registry:
        if rec.get('google_play_id'):
            rec['google_play_metadata'] = fetch_google_metadata(session, rec['google_play_id'])
            rec['google_play_url'] = rec['google_play_metadata'].get('url') or rec.get('google_play_url')
        else:
            rec['google_play_metadata'] = {}
    save_json(REGISTRY_PATH, {'generated_at': now_iso(), 'source': 'Google Play', 'apps': registry})

    diagnostics = {
        'started_at': now_iso(),
        'source': 'Google Play',
        'settings': {
            'max_reviews_per_stream': args.max_reviews_per_stream,
            'google_languages': parse_csv_arg(args.google_languages),
            'google_sorts': parse_csv_arg(args.google_sorts),
            'fresh': args.fresh,
        },
        'apps': [],
    }
    languages = [x.lower() for x in parse_csv_arg(args.google_languages)]
    sorts = [x.upper() for x in parse_csv_arg(args.google_sorts)]

    print('\n============================================================')
    print(' GOOGLE PLAY — BANKING & FINTECH COMPETITOR TRACKER')
    print('============================================================')
    print(f'Apps selected: {len(registry)}')
    print(f'Review streams: {", ".join(languages)} × {", ".join(sorts)}')
    print('Store metadata: current Google Play rating + reported counts')
    print('============================================================\n')

    for idx, rec in enumerate(registry, 1):
        print(f'[{idx}/{len(registry)}] {rec["app_name"]}')
        app_diag = {'app_key': rec['app_key'], 'app_name': rec['app_name'], 'google_play': {}, 'stored_before': len(stored)}
        if rec.get('google_play_id'):
            for lang in languages:
                for sort_name in sorts:
                    d = {}
                    fetched = collect_google_stream(rec, lang, sort_name, args.max_reviews_per_stream, d)
                    app_diag['google_play'][f'{lang}:{sort_name}'] = d
                    for row in fetched:
                        stored[row['review_id']] = enrich_review(row)
                    print(f'  Google Play [{lang}/{sort_name}]: {len(fetched)}')
        else:
            app_diag['google_play'] = {'status': 'not_collected', 'reason': 'no_validated_app_id', 'discovery': rec.get('google_play_discovery', {})}
            print('  Google Play: NO VALIDATED APP ID')
        app_diag['stored_after'] = len(stored)
        diagnostics['apps'].append(app_diag)
        print()

    active_keys = {r['app_key'] for r in registry}
    review_list = [r for r in stored.values() if r.get('platform') == 'Google Play' and r.get('app_key') in active_keys]
    review_list.sort(key=lambda x: str(x.get('review_date', '')), reverse=True)

    stamp = now_iso()
    save_json(REVIEWS_PATH, {'generated_at': stamp, 'source': 'Google Play', 'is_demo': False, 'review_count': len(review_list), 'reviews': review_list})
    save_csv(CSV_PATH, review_list)
    save_json(SUMMARY_PATH, aggregate(review_list, registry))
    update_store_history(registry)

    diagnostics.update({'finished_at': now_iso(), 'final_unique_review_count': len(review_list), 'stored_google_play_reviews': len(review_list)})
    save_json(DIAGNOSTICS_PATH, diagnostics)

    print('============================================================')
    print(' COLLECTION COMPLETE')
    print(f'Unique stored reviews : {len(review_list):,}')
    print(f'CSV export             : {CSV_PATH}')
    print(f'Store history          : {HISTORY_PATH}')
    print('============================================================')


if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(1)
    except Exception as exc:
        print("\nSCRAPER ERROR")
        print(exc)
        sys.exit(1)
