# Bank Competitors Tracker — Google Play

Web-based tracker of Indonesian banking and fintech app **ratings and user reviews from Google Play**, benchmarked against **Allo Bank**.

**Source:** Google Play (Indonesia storefront) only. No App Store data.

## What the dashboard shows

- Allo Bank review rating vs. 22 peers (digital banks, conventional bank apps, non-bank fintech)
- Play Store rating and total store ratings (from the app listing) next to the average rating of collected written reviews
- Gap vs. Allo Bank per app, sentiment by industry, top negative issues, review topics, monthly trend
- Recent negative reviews and a link to each app's Play Store page

## Run

```powershell
python -m pip install -r requirements.txt
python scraper\scrape_reviews.py
```

Or double-click `run_scraper.bat`, then `open_dashboard.bat` and go to http://localhost:8000/

Options: `--max-reviews-per-stream 0` (unlimited), `--google-languages id,en`, `--google-sorts NEWEST,RATING,HELPFUL`, `--only-app allo_bank,jago`, `--skip-discovery`, `--fresh`.

Runs merge into `data/reviews.json` by review ID, so repeated runs build a longer history. GitHub Actions (`.github/workflows/update-dashboard.yml`) refreshes the data daily and deploys to GitHub Pages.

## Files

- `data/apps_catalog.json` apps to track
- `data/app_registry.json` validated Play Store IDs and store metadata (rating, ratings count, installs)
- `data/reviews.json` all collected reviews with sentiment/topic/issue labels
- `data/summary.json` dashboard aggregates
- `data/collection_diagnostics.json` per-app collection diagnostics

## Notes

- Written reviews are not the same as total store ratings; the dashboard shows both.
- Sentiment, topic and issue labels come from a transparent keyword baseline (`scraper/text_analysis.py`), not an AI model.
- Apps without a validated Play Store ID (currently SeaBank Indonesia and PermataX) have no reviews until a package ID is added to `KNOWN_GOOGLE_IDS` in `scraper/scrape_reviews.py` or discovery succeeds.
- `reviews.json` is about 29 MB, so the first page load is slow.
