# Methodology

## Objective

Track and compare Google Play ratings and written user reviews for Indonesian banking and fintech apps, with Allo Bank as the main reference.

## Ratings vs. reviews

- **Play Store rating / store ratings**: the score and rating count shown on the app listing, stored in `app_registry.json`.
- **Review avg.**: the average star rating of the written reviews collected in this dataset. Ratings without written text are not included, so this can differ from the store rating.

## Collection

For each app the collector uses the package ID and continuation-token pagination (`google-play-scraper`), optionally across Indonesian/English contexts and NEWEST, RATING and HELPFUL sort orders. Results are merged by review ID. Pagination ends when the endpoint stops returning a new token or a request fails.

## App discovery

1. Known package ID, validated against app title/developer
2. `google-play-scraper` search
3. Play Store search-page HTML fallback

Low-confidence matches are rejected instead of collected.

## Classification

Sentiment, topic and primary issue are assigned by keyword rules plus the star rating (1-2 stars = negative, 4-5 = positive). 'General' means no rule matched.

## Repeated collection

Existing reviews are kept and new IDs are added on each run. Use `--fresh` to start over.

## Diagnostics

`data/collection_diagnostics.json` records discovery method, pagination calls, termination reason, errors and unique counts per app.
