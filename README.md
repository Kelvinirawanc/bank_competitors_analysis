# Banking & Fintech App Competitive Intelligence — Full Review Collector

**Main benchmark:** Allo Bank  
**Platforms:** Google Play + Apple App Store (Indonesia storefront)  
**Data:** Public written reviews, ratings, review dates, app versions, reviewer names where exposed, helpful votes where exposed, and developer replies where exposed.

## What changed in this build

The previous scraper intentionally stopped at relatively small limits and relied too heavily on first-pass app discovery. This build is designed to collect the **maximum public written review coverage available**.

### Google Play

- continuation-token pagination
- no artificial review cap by default
- multiple sort passes: NEWEST, RATING, HELPFUL
- multiple UI language passes: Indonesian + English
- merges duplicate review IDs
- validates every discovered package ID
- retries discovery through several routes
- stores detailed diagnostics

### Apple App Store

- Indonesia storefront
- pages 1–10
- mostRecent + mostHelpful
- continues through page holes instead of stopping at the first empty page
- deduplicates review IDs
- stores diagnostics

### No sample data

This version contains **no demo review dataset**. `data/reviews.json` starts empty and is populated only by the scraper.

## Output files

- `data/reviews.json` — full structured review dataset
- `data/reviews.csv` — flat export of the same reviews
- `data/app_registry.json` — validated store IDs and store metadata
- `data/collection_diagnostics.json` — discovery and pagination diagnostics
- `data/summary.json` — dashboard aggregates

## Important: what “all reviews” means technically

The scraper is built to retrieve **all written reviews that the public endpoints expose during the run**, not to fabricate a guarantee that every historical rating/review on the stores is accessible.

Google Play review pagination can traverse a large accessible set, but the public endpoint/library can still impose practical limits or encounter anti-bot/request failures.

Apple's public customer-review RSS feed is a rolling window. Current testing indicates approximately 10 pages of about 50 written reviews per app/storefront/sort. Apple's official App Store Connect API can list all customer reviews for an app, but it requires authenticated access to an app in the developer's account; that is not assumed for competitor apps.

Therefore, the correct portfolio claim is:

> **Maximum publicly accessible written-review collection with repeated incremental backfills.**

## Project structure

```text
bank_competitors_full/
├── index.html
├── requirements.txt
├── run_scraper.bat
├── open_dashboard.bat
├── README.md
├── css/
│   └── style.css
├── js/
│   └── dashboard.js
├── scraper/
│   ├── scrape_reviews.py
│   └── text_analysis.py
├── data/
│   ├── apps_catalog.json
│   ├── app_registry.json
│   ├── collection_diagnostics.json
│   ├── reviews.json
│   └── summary.json
└── docs/
    └── methodology.md
```

## Setup

Open the folder in VS Code.

Check Python:

```powershell
python --version
```

Run the scraper:

```powershell
python -m pip install -r requirements.txt
python scraper\scrape_reviews.py
```

Or double-click:

```text
run_scraper.bat
```

Then open:

```text
open_dashboard.bat
```

Dashboard:

```text
http://localhost:8000/
```

## Full run configuration

`run_scraper.bat` runs:

```text
--max-reviews-per-stream 0
--google-languages id,en
--google-sorts NEWEST,RATING,HELPFUL
--apple-pages 10
--apple-sorts MOST_RECENT,MOST_HELPFUL
```

`0` means the Google Play stream continues until the endpoint stops returning a new continuation token or an error occurs.

## Build a bigger historical dataset

The most useful workflow is repeated collection:

```text
Run 1
  -> collect public review window
  -> save reviews.json

Run 2
  -> collect public review window again
  -> merge by review_id
  -> save new rows

Run 3
  -> collect again
  -> merge new IDs
```

The scraper does not delete old collected reviews unless you use `--fresh`.

## Troubleshooting zero reviews

Open:

```text
data\collection_diagnostics.json
```

For each app, inspect:

```text
google_play.*.status
  selected package ID
  validation score
  pagination calls
  raw_reviews
  termination
  error

app_store.*.pages_seen
app_store.*.empty_pages
app_store.*.errors
```

That tells you whether the problem is:

- app discovery
- package/app ID validation
- request blocking
- pagination termination
- a genuinely empty exposed review stream

## Data quality fields

Each review retains:

- platform
- store country
- app
- rating
- title
- text
- review date
- app version
- reviewer name if exposed
- helpful votes if exposed
- developer response if exposed
- source URL
- collection language/sort where applicable
- sentiment
- sentiment confidence
- topic
- topic confidence
- primary issue
- validation status
- quality score

## AI

The scraper does not call AI and does not require an AI API key. The deterministic sentiment/topic layer is intentionally transparent.

A future AI step can be added for ambiguous reviews, multi-topic complaints, summarization, or manual-label evaluation.

## Sources

- Google Play package: `google-play-scraper`
- Apple public customer-review RSS JSON feed
- Apple's official App Store Connect Customer Reviews API documentation: https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews

See `docs/methodology.md` for the full methodology and limitations.
