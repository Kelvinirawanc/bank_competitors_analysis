# Review Collection Methodology

## Objective

Collect the maximum public **written review data** exposed by Google Play and the Indonesia App Store for the selected banking and fintech apps, with Allo Bank as the main reference.

## Important distinction

A store's displayed rating count is not the same thing as the number of written reviews that a public review endpoint exposes. Ratings without written comments are not part of this review-text dataset.

The goal of this project is therefore:

> **maximum publicly accessible written-review coverage + repeated incremental collection + deduplication**

It is not a claim that every rating or every historical review in the store is technically available through public endpoints.

## Google Play strategy

The collector uses a package ID and continuation-token pagination rather than stopping after the first 200 reviews.

For each app it can run multiple passes:

- Indonesian context (`id`)
- English context (`en`)
- newest-first
- rating-ordered
- helpfulness-ordered

The passes are merged by `review_id`.

This matters because a single newest-first pass may not surface the same portion of the review set as another sort order.

A zero artificial per-stream limit is used by default. Pagination terminates when the endpoint no longer produces a new continuation token or a request fails.

## App discovery

Each app can be discovered through:

1. validated known package IDs where available;
2. `google-play-scraper` search;
3. direct Google Play store-search HTML as a fallback.

Candidates are scored against the expected app name, search term, required keywords and developer/title metadata. Low-confidence matches are rejected rather than silently collected.

## Apple App Store strategy

The collector uses the public customer-review RSS JSON feed for the **Indonesia storefront**.

Each run checks:

- `mostRecent` pages 1–10
- `mostHelpful` pages 1–10

The scraper deliberately continues across the page window even when one page is empty because current observations show that the public feed can have empty pages before another populated page.

Rows are merged by Apple review ID.

## Apple historical limitation

The public RSS feed is a rolling, practical window rather than a full historical archive. Current technical observations put the ceiling at approximately 10 pages of roughly 50 written reviews per app/storefront/sort. Apple's documented App Store Connect API can list all customer reviews for an app, but it requires authorized access to the developer's own app resources.

Because this project compares competitor apps, that authorized API is not assumed to be available for the competitors.

## Repeated collection

Run the scraper periodically. Existing rows are merged by stable review ID, so later runs add new reviews without creating duplicates.

For example:

```text
Day 1 -> collect current public window
Day 2 -> collect current public window -> merge new IDs
Day 3 -> collect current public window -> merge new IDs
```

This is the practical way to build a longer historical dataset over time.

## Diagnostics

`data/collection_diagnostics.json` records:

- discovery method
- candidate count
- validation score
- selected app ID
- Google Play language/sort
- number of pagination calls
- Apple pages inspected
- empty pages
- request errors
- termination reason
- raw and unique counts

This makes a `0 reviews` result auditable instead of ambiguous.

## Sources

Google Play review collection uses `google-play-scraper`, which supports review retrieval and sorting/pagination patterns. A separate contemporary project demonstrates full-history style ingestion with continuation tokens, while an upstream issue documents that the older `reviews_all` helper can have limitations on apps with very large review volumes.

Apple's official App Store Connect Customer Reviews API documents the authorized endpoint for listing all customer reviews for an app.

The public Apple RSS feed's practical 10-page/roughly-500-written-review window is documented by current third-party testing and should be treated as a technical limitation of that public feed rather than as Apple's official historical data specification.
