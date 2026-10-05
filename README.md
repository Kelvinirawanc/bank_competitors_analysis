# Allo Bank™ Competitive Intelligence Monitor

A polished Google Play competitive-intelligence dashboard for Allo Bank™ and 24 selected Indonesian banking / fintech apps.

## Dashboard views

- **Overall** — compare all apps with Category and App filters.
- **Allo Bank™** — benchmark Allo Bank™ against the digital-bank peer set.

## Data package

The dashboard uses the newly supplied 5 Oct 2026 Google Play web extracts in `data/`:

- `app_metrics_latest_web_2026-10-05.csv`
- `reviews_surfaced_web_2026-10-05.csv`
- `method_and_limits_2026-10-05.csv`

Run:

```bash
python build_static_data.py
```

This generates `data/dashboard_data.json`, the browser-ready layer used by the frontend.

## Front-end experience

The UI is designed as an operational monitoring dashboard: live-style status treatment, local clock, manual refresh control, periodic refresh polling, responsive filters, benchmark charts, customer-voice signals, and an Allo Bank focus view.

The interface does not expose implementation wording such as "static dataset". The data remains traceable through the supplied CSV files and methodology document in `data/`.

## Local run

Double-click `open_dashboard.bat`, or run:

```bash
python -m http.server 8000
```

then open `http://localhost:8000`.

## GitHub Pages

The workflow in `.github/workflows/deploy-pages.yml` rebuilds `dashboard_data.json` and deploys the dashboard to GitHub Pages.

## Notes

The customer-voice area uses public review summaries surfaced in the supplied Google Play extraction. Where star scores are unavailable, the dashboard assigns a directional text signal from the supplied summary.

Data analysis & dashboard by Kelvin Irawan.
