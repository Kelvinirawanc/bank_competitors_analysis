# Bank Competitors Tracker (Google Play)

A web-based dashboard that tracks and compares **Google Play ratings and user reviews** of Indonesian banking and fintech apps, with **Allo Bank** as the main benchmark.

**Data source:** Google Play, Indonesia storefront (public listings and written reviews). No App Store data is used.

Built with Python (scraper), HTML, CSS, JavaScript and Chart.js (dashboard).

---

## Table of contents

1. [Purpose](#purpose)
2. [Apps tracked](#apps-tracked)
3. [Dashboard features](#dashboard-features)
4. [Project structure](#project-structure)
5. [Quick start](#quick-start)
6. [Scraper options](#scraper-options)
7. [Data files](#data-files)
8. [Review fields](#review-fields)
9. [Methodology](#methodology)
10. [Automation with GitHub Actions](#automation-with-github-actions)
11. [Deploy to GitHub Pages](#deploy-to-github-pages)
12. [Adding or fixing an app](#adding-or-fixing-an-app)
13. [Troubleshooting](#troubleshooting)
14. [Limitations](#limitations)
15. [Author and disclaimer](#author-and-disclaimer)

---

## Purpose

This project answers questions such as:

- How does the Allo Bank app rating compare with other digital banks, conventional bank apps and non-bank fintech apps?
- What do users complain about most (login/OTP, crashes, top-up/payment failures, customer service, fees)?
- How do sentiment and ratings change month by month?
- Which competitors are doing better or worse than Allo Bank, and by how much?

---

## Apps tracked

The catalog has 25 apps in three groups. Allo Bank is the main benchmark.

**Digital banks:** Allo Bank (main), Jago, SeaBank Indonesia, blu by BCA Digital, neobank (Neo Commerce), Bank Aladin Syariah, Superbank, Krom Bank, hi by hibank, Bank Raya, MotionBank (MNC Bank)

**Conventional bank apps:** myBCA, BCA mobile, Livin' by Mandiri, BRImo, wondr by BNI, OCTO Mobile (CIMB Niaga), PermataX, D-Bank PRO (Danamon), OCBC Mobile

**Non-bank fintech (payments, paylater, cashback):** GoPay, OVO, DANA, ShopeePay, LinkAja

The list is defined in `data/apps_catalog.json`.

> At the time of the last build, SeaBank Indonesia and PermataX had no validated Play Store package ID, so they have no reviews yet. See [Adding or fixing an app](#adding-or-fixing-an-app).

---

## Dashboard features

- **KPI cards:** Allo Bank review rating, reviews analysed, negative share, actionable reviews
- **Filters:** industry and app, with a reset button
- **Average rating chart:** average star rating of collected reviews per app
- **Sentiment by industry:** positive, neutral and negative counts
- **Top negative issues:** most common problems in negative reviews
- **Review topics:** what users talk about (login, transactions, UI/UX and so on)
- **Trend:** monthly review volume and average rating
- **App comparison table:**
  - Play Store rating and total store ratings (from the app listing)
  - Reviews collected and average rating of those reviews
  - Gap vs Allo Bank (green = above Allo Bank, red = below)
  - Positive %, negative % and 1-2 star %
  - Direct link to the Play Store page
- **Review explorer:** the most recent negative written reviews

---

## Project structure

```text
bank_competitors_analysis/
├── index.html                      # Dashboard page
├── css/
│   └── style.css                   # Dashboard styling
├── js/
│   └── dashboard.js                # Filtering, aggregation and charts
├── scraper/
│   ├── scrape_reviews.py           # Google Play collector
│   └── text_analysis.py            # Sentiment, topic and issue rules
├── data/
│   ├── apps_catalog.json           # Apps to track (input)
│   ├── app_registry.json           # Validated Play Store IDs and listing metadata
│   ├── reviews.json                # All collected reviews with labels
│   ├── reviews.csv                 # Flat export (created by the scraper)
│   ├── summary.json                # Pre-computed aggregates
│   └── collection_diagnostics.json # Per-app collection log
├── docs/
│   └── methodology.md              # Methodology notes
├── .github/workflows/
│   └── update-dashboard.yml        # Daily refresh and GitHub Pages deploy
├── requirements.txt
├── run_scraper.bat                 # Windows: run the scraper
├── open_dashboard.bat              # Windows: open the dashboard locally
└── README.md
```

---

## Quick start

### 1. Requirements

- Python 3.10 or newer (`python --version`)
- Internet access to Google Play

### 2. Install and run the scraper

```powershell
python -m pip install -r requirements.txt
python scraper\scrape_reviews.py
```

On Windows you can double-click `run_scraper.bat` instead. Collection can take a long time because each app is read in several passes.

### 3. Open the dashboard

Double-click `open_dashboard.bat`, or run:

```powershell
python -m http.server 8000
```

Then open http://localhost:8000/

> The dashboard loads JSON files with `fetch`, so it must be opened through a local web server. Opening `index.html` directly from the file system will not work.

---

## Scraper options

```powershell
python scraper\scrape_reviews.py [options]
```

| Option | Default | Description |
|---|---|---|
| `--max-reviews-per-stream N` | `0` | `0` = collect until pagination ends. A positive number caps each language/sort pass. |
| `--google-languages id,en` | `id,en` | Review language contexts to run. |
| `--google-sorts NEWEST,RATING,HELPFUL` | all three | Sort orders to run. Results are merged and de-duplicated. |
| `--only-app allo_bank,jago` | all apps | Collect only the listed `app_key` values. |
| `--skip-discovery` | off | Reuse package IDs already stored in `app_registry.json`. Faster for repeat runs. |
| `--fresh` | off | Ignore previously stored reviews and start from zero. |

Examples:

```powershell
# Full run (what run_scraper.bat does)
python scraper\scrape_reviews.py --max-reviews-per-stream 0 --google-languages id,en --google-sorts NEWEST,RATING,HELPFUL

# Quick refresh of the newest Indonesian reviews only
python scraper\scrape_reviews.py --skip-discovery --max-reviews-per-stream 200 --google-languages id --google-sorts NEWEST

# Only Allo Bank and Jago
python scraper\scrape_reviews.py --only-app allo_bank,bank_jago
```

---

## Data files

| File | Description |
|---|---|
| `apps_catalog.json` | Input list: app key, name, company, industry, role, search term and required keywords for matching. |
| `app_registry.json` | Output of app discovery: validated Play Store package ID, URL and listing metadata (title, developer, store rating, number of ratings, installs, last update). |
| `reviews.json` | All unique reviews collected so far, with sentiment, topic and issue labels. |
| `reviews.csv` | Same reviews as a flat CSV for Excel or SQL work. |
| `summary.json` | Aggregates (overall, per app, per industry, topics, issues, monthly trend). |
| `collection_diagnostics.json` | Per-app log: discovery result, pagination calls, termination reason, errors and unique counts. |

---

## Review fields

Each review in `reviews.json` contains:

| Field | Meaning |
|---|---|
| `review_id` | Stable ID (`gp:` + Google Play review ID), used for de-duplication |
| `app_key`, `app_name`, `company`, `industry`, `role` | App identity from the catalog |
| `platform`, `store_country` | `Google Play`, `id` |
| `rating` | Star rating, 1 to 5 |
| `review_text`, `review_title` | Written review (Google Play has no title) |
| `review_date` | Review timestamp |
| `app_version` | App version when the review was written |
| `user_name`, `thumbs_up` | Reviewer name and helpful votes, where exposed |
| `developer_reply` | Developer response, where exposed |
| `source_url` | Play Store URL of the app |
| `collection_language`, `collection_sort` | Which pass collected the review |
| `scraped_at` | Collection timestamp |
| `sentiment`, `sentiment_confidence` | Positive, Neutral or Negative, plus a confidence value |
| `topic`, `topic_confidence` | Main topic of the review |
| `primary_issue` | Main issue (used for negative reviews) |
| `validation_passed`, `quality_score`, `actionable` | Data quality flags |

---

## Methodology

### Ratings vs reviews

- **Play Store rating / store ratings:** the score and rating count shown on the app listing. Stored in `app_registry.json`.
- **Review avg.:** the average star rating of the *written reviews collected in this dataset*. Star ratings without written text are not included, so this number can differ from the store rating.

The dashboard shows both so you can see the difference.

### Collection

For each app, the scraper uses the Play Store package ID and continuation-token pagination (`google-play-scraper`). It can run several passes (Indonesian and English, newest, rating and helpful sort orders). All passes are merged by review ID, so duplicates are removed. Pagination stops when the endpoint stops returning a new token or a request fails.

### App discovery and validation

1. Try a known package ID and check it against the expected app title and developer.
2. Search with `google-play-scraper`.
3. Fall back to parsing the Play Store search page.

Candidates are scored against the expected name, search term and required keywords. Low-confidence matches are rejected instead of being collected.

### Classification

Classification is a transparent keyword baseline in `scraper/text_analysis.py`. No AI model or API key is used.

- **Sentiment:** 1-2 stars = Negative, 4-5 stars = Positive. For 3 stars, positive vs negative keyword counts decide, otherwise Neutral.
- **Topic:** the topic with the most keyword matches wins (Login & KYC, Transaction, Customer Service, Performance & Bugs, Promo & Benefits, UI / UX, Security, Fees & Limits). No match = General.
- **Primary issue:** the issue with the most keyword matches wins (for example Login / OTP, App error / crash, Top up / payment, Balance / refund). No match = General.
- **Actionable:** the review has at least 12 characters of text.

### Repeated collection

Existing reviews are kept and only new IDs are added on each run, so the dataset grows over time. Use `--fresh` to rebuild from scratch.

---

## Automation with GitHub Actions

The workflow `.github/workflows/update-dashboard.yml`:

- runs every day at 07:00 WIB (00:00 UTC) and can also be started manually (`workflow_dispatch`)
- installs dependencies and runs the scraper (newest Indonesian reviews, capped per stream)
- validates the generated JSON files
- commits the updated `data/` files back to the repository
- deploys the site to GitHub Pages

---

## Deploy to GitHub Pages

1. Push the project to a GitHub repository.
2. Go to **Settings > Pages** and set the source to **GitHub Actions**.
3. Go to **Actions**, open **Update Bank Competitors Tracker** and click **Run workflow**.
4. After the run finishes, the dashboard is available at the Pages URL shown in the deploy step.

> `reviews.json` is about 29 MB. This is within GitHub's file limit, but the first page load is slow. If it grows much larger, consider splitting the data per app or loading only `summary.json` first.

---

## Adding or fixing an app

**Add a new app**

1. Add an entry to `data/apps_catalog.json`:

```json
{
  "app_key": "example_bank",
  "app_name": "Example Bank",
  "company": "Example Bank Indonesia",
  "industry": "Digital Banks",
  "role": "Peer",
  "search_term": "Example Bank",
  "required_terms": ["example"]
}
```

2. Run `python scraper\scrape_reviews.py --only-app example_bank`.

`industry` should be one of `Digital Banks`, `Conventional Banking Apps` or `Non-bank Fintech`, because the dashboard filter uses these values.

**Fix an app with no reviews**

If discovery cannot validate a package ID (currently SeaBank Indonesia and PermataX):

1. Open the app on Google Play and copy the `id=` value from the URL, for example `https://play.google.com/store/apps/details?id=com.example.app` gives `com.example.app`.
2. Add it to `KNOWN_GOOGLE_IDS` in `scraper/scrape_reviews.py`:

```python
KNOWN_GOOGLE_IDS = {
    # ...
    "seabank": "com.example.app",
}
```

3. Run `python scraper\scrape_reviews.py --only-app seabank`.

Check `data/collection_diagnostics.json` and `google_play_discovery` in `app_registry.json` to see why discovery failed.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Dashboard shows "Data loading error" | Open it through a local server (`python -m http.server 8000`), not by double-clicking `index.html`. |
| Dashboard says "No live data yet" | `data/reviews.json` is empty. Run the scraper. |
| An app has 0 reviews | Look at `google_play_discovery` in `app_registry.json` and the app entry in `collection_diagnostics.json`. Usually the package ID was not validated. |
| Scraper stops early or errors | Google Play may be rate limiting. Wait and rerun with `--skip-discovery`. Merged data is kept. |
| Charts are blank | Chart.js loads from a CDN. Check your internet connection. |
| Dashboard is slow to load | `reviews.json` is large. Use a modern browser, or split the data per app. |

---

## Limitations

- **Written reviews only.** Star ratings without text are not in the review dataset. Store-wide rating counts are shown separately from the app listing.
- **Coverage is not guaranteed.** The scraper collects what the public Google Play endpoint exposes during a run. It can be limited by rate limiting or request failures, and it cannot guarantee every historical review.
- **Sample, not census.** Review volumes differ between apps, so compare percentages and averages, not raw counts.
- **Keyword-based classification.** Reviews are short, informal and mix Indonesian and English. Many fall into `General`, and sarcasm or multi-topic reviews can be misclassified.
- **Google Play only.** iOS users are not represented.
- **Listing metadata is a snapshot** from the last run of app discovery.

---

## Author and disclaimer

Data analysis and dashboard by **Kelvin Irawan**.

Data is compiled from publicly available Google Play listings and reviews for analytical and educational purposes. This project is not affiliated with or endorsed by any of the companies listed.
