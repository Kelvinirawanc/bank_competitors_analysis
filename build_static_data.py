#!/usr/bin/env python3
"""Build the browser-ready dataset for the Allo Bank Competitive Intelligence dashboard.

Input files are the latest supplied Google Play web extracts in /data.
The browser reads only dashboard_data.json, while the raw CSVs remain available
in /data for auditability and future refreshes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

METRICS = DATA / "app_metrics_latest_web_2026-10-05.csv"
REVIEWS = DATA / "reviews_surfaced_web_2026-10-05.csv"
METHOD = DATA / "method_and_limits_2026-10-05.csv"
OUTPUT = DATA / "dashboard_data.json"
FOCUS_PACKAGE = "com.alloapp.yump"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_compact_number(value: str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace(",", "")
    if not text:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMB])?\+?", text)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(match.group(2), 1)
    return int(round(number * multiplier))


def normalize_category(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return {
        "digital banks": "Digital Banks",
        "conventional banks": "Conventional Banks",
        "non-bank competitors": "Non-bank Competitors",
    }.get(raw, (value or "Other").strip() or "Other")


def stable_id(package_id: str, reviewer: str, review_date: str, summary: str) -> str:
    raw = "|".join([package_id, reviewer, review_date, summary]).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def clean(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text if text and text.lower() not in {"nan", "none", "n/a"} else None


TOPIC_RULES = [
    ("QRIS & Payments", ["qris", "payment", "payments", "merchant", "pay"]),
    ("Transactions & Transfer", ["transaction", "transactions", "transfer", "transfers", "withdrawal", "withdraw", "top-up", "top up", "balance", "refund"]),
    ("Login & Verification", ["otp", "login", "logged in", "sign-in", "signin", "verification", "verify", "pin", "password", "biometric", "account setup", "setup"]),
    ("App Performance", ["lag", "slow", "loading", "reload", "glitch", "freeze", "failing", "system error", "system-disruption", "stuck", "unusable"]),
    ("Customer Service", ["customer service", "customer-service", "complaint", "handling", "service experience", "management"]),
    ("Fees, Rates & Rewards", ["fee", "fees", "promo", "promotions", "reward", "rewards", "cashback", "free transfer", "yield", "interest", "affordability"]),
    ("Loans & Credit", ["loan", "paylater", "credit", "borrowing"]),
    ("Cards & E-money", ["card", "e-money", "atm"]),
    ("Product Features", ["feature", "features", "savings", "deposit", "saving pockets", "home", "navigation", "usability", "ui", "interface", "ads"]),
]

POSITIVE_TERMS = [
    "positive", "mostly positive", "praise", "praising", "good", "great", "very good", "easy",
    "simple", "successful", "reliable", "useful", "helpful", "benefit", "benefits", "fast",
    "convenient", "recommended", "recommend", "clean", "value", "flexible", "smooth", "practical",
    "approval", "likes", "like", "premium-looking", "good experience"
]
NEGATIVE_TERMS = [
    "complaint", "concern", "issue", "issues", "problem", "problems", "failed", "failure", "failing",
    "error", "errors", "difficulty", "difficult", "slow", "lag", "glitch", "stuck", "deducted", "delayed",
    "delay", "unable", "trouble", "friction", "dissatisfaction", "logout", "loop", "recurring", "poor",
    "worst", "not great", "criticizes", "criticize", "blocked", "inaccessible", "unusable", "incorrect",
    "disruption", "disruptions", "misleading", "intrusive", "technical issue"
]


def term_hits(text: str, terms: list[str]) -> int:
    normalized = (text or "").lower()
    total = 0
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
        total += len(re.findall(pattern, normalized))
    return total


def classify_topic(text: str) -> str:
    best_label = "General"
    best_score = 0
    for label, words in TOPIC_RULES:
        score = term_hits(text, words)
        if score > best_score:
            best_label, best_score = label, score
    return best_label


def classify_tone(text: str, score: float | None = None) -> str:
    # Use star score when the source exposes it. Otherwise use the supplied review summary.
    if score is not None:
        if score >= 4:
            return "Positive"
        if score == 3:
            return "Mixed"
        return "Concern"
    positive = term_hits(text, POSITIVE_TERMS)
    negative = term_hits(text, NEGATIVE_TERMS)
    if positive and negative:
        return "Mixed"
    if negative:
        return "Concern"
    if positive:
        return "Positive"
    return "Neutral"


def safe_float(value: str | None) -> float | None:
    value = clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_methodology(rows: list[dict[str, str]]) -> dict[str, str]:
    return {clean(r.get("item")) or "": clean(r.get("value")) or "" for r in rows}


def build() -> None:
    metrics_rows = read_csv(METRICS)
    review_rows = read_csv(REVIEWS)
    method_rows = read_csv(METHOD) if METHOD.exists() else []
    method = parse_methodology(method_rows)

    apps: list[dict[str, Any]] = []
    for row in metrics_rows:
        package_id = clean(row.get("package_id"))
        if not package_id:
            continue
        is_focus = package_id == FOCUS_PACKAGE or (clean(row.get("benchmark_role")) or "").lower() == "own bank"
        app_name = clean(row.get("app_name")) or package_id
        apps.append({
            "app_key": package_id,
            "app_name": app_name,
            "display_name": "Allo Bank™" if is_focus else app_name,
            "industry": normalize_category(row.get("category")),
            "benchmark_role": "Own Bank" if is_focus else "Competitor",
            "package_id": package_id,
            "google_play_url": clean(row.get("source_url")),
            "store_rating": safe_float(row.get("rating")),
            "store_reviews_display": clean(row.get("review_count_display")),
            "store_reviews_numeric": parse_compact_number(row.get("review_count_display")),
            "downloads_display": clean(row.get("downloads_display")),
            "downloads_numeric": parse_compact_number(row.get("downloads_display")),
            "store_updated": clean(row.get("app_updated_on")),
            "is_focus": is_focus,
        })

    apps.sort(key=lambda a: (0 if a["is_focus"] else 1, a["app_name"].lower()))
    app_by_pkg = {a["package_id"]: a for a in apps}

    reviews: list[dict[str, Any]] = []
    for r in review_rows:
        package_id = clean(r.get("package_id"))
        app = app_by_pkg.get(package_id or "")
        if not app:
            continue
        reviewer = clean(r.get("reviewer_name")) or "Google Play user"
        review_date = clean(r.get("review_date"))
        summary = clean(r.get("review_summary")) or "Public review signal surfaced."
        score = safe_float(r.get("score"))
        helpful = int(round(safe_float(r.get("helpful_votes")) or 0))
        reviews.append({
            "review_id": stable_id(package_id or "", reviewer, review_date or "", summary),
            "app_key": package_id,
            "app_name": app["display_name"],
            "industry": app["industry"],
            "reviewer_name": reviewer,
            "review_date": review_date,
            "rating": score,
            "rating_available": score is not None,
            "review_text": summary,
            "review_type": "Public review signal",
            "thumbs_up": helpful,
            "tone": classify_tone(summary, score),
            "topic": classify_topic(summary),
            "source_url": clean(r.get("source_url")) or app["google_play_url"],
        })

    rated = [a for a in apps if a["store_rating"] is not None]
    categories: dict[str, int] = {}
    for a in apps:
        categories[a["industry"]] = categories.get(a["industry"], 0) + 1

    tones = ["Positive", "Mixed", "Neutral", "Concern"]
    tone_counts = {t: sum(1 for r in reviews if r["tone"] == t) for t in tones}
    topic_counts: dict[str, int] = {}
    for r in reviews:
        topic_counts[r["topic"]] = topic_counts.get(r["topic"], 0) + 1

    report_date = method.get("report_date") or "2026-10-05"
    last_app_update = max((a["store_updated"] for a in apps if a["store_updated"]), default=None)
    latest_review = max((r["review_date"] for r in reviews if r["review_date"]), default=None)
    source_label = method.get("high_level_source") or "Google Play public app pages / search-indexed current page content"
    generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "generated_at_utc": generated_at,
        "source_report_date": report_date,
        "source_snapshot_date": report_date,
        "source": "Google Play",
        "country": "Indonesia",
        "focus_app_key": FOCUS_PACKAGE,
        "focus_app_name": "Allo Bank™",
        "apps": apps,
        "reviews": reviews,
        "summary": {
            "app_count": len(apps),
            "competitor_count": sum(not a["is_focus"] for a in apps),
            "review_signal_count": len(reviews),
            "apps_with_rating": len(rated),
            "categories": categories,
            "tone_counts": tone_counts,
            "topic_counts": dict(sorted(topic_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            "last_app_update": last_app_update,
            "latest_review_date": latest_review,
            "source_files": [METRICS.name, REVIEWS.name, METHOD.name],
        },
        "ui": {
            "last_updated_label": "05 Oct 2026",
            "status_label": "Monitoring",
            "source_label": "Google Play · Indonesia",
            "coverage_label": f"{len(apps)} apps · {len(reviews)} surfaced review signals",
            "method_source": source_label,
        },
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {OUTPUT.name}: {len(apps)} apps, {len(reviews)} review signals, {len(rated)} rated apps.")


if __name__ == "__main__":
    build()
