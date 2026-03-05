# LeadIntel — AI Lead Scoring for Property-Management Sales

LeadIntel turns a list of apartment-property leads into a ranked, explained pipeline for a sales team. For each lead it researches the property across the web, scores how promising it is, explains *why*, and drafts a personalized outreach email, all inside a Streamlit app.

It is built for a leasing-automation SaaS selling to residential property managers (the email prompts are written for an SDR at EliseAI).

<p align="center">
  <img src="assets/demo.gif" alt="LeadIntel demo" width="800"/>
</p>

---

## Features

- **Lead management UI**: add leads from the sidebar, edit ZIP codes inline, delete rows, and choose which leads to run.
- **Automatic enrichment** for every property:
  - **Apartments.com**: unit count, review count, 1–2 star complaints, management company
  - **Zillow**: active listings and floorplan count
  - **Account fit lookup** (Gemini): manager portfolio size, property type and property-management software (PMS) vendor
  - **U.S. Census**: population, employment and housing occupancy for the ZIP code
  - **Buying triggers** (Gemini + Google Search): ownership changes, lease-up / new construction, leasing-role hiring, expansion and tech changes from the last 18 months
- **Transparent scoring**: a 0–1 score, a priority bucket (High / Medium / Low / Needs Review), a per-component breakdown and plain-English reasons.
- **AI-drafted outreach email** grounded only in the facts that were found, with one-click redraft.
- **Two-level caching** so re-runs cost no API credits: scraped pages and computed features/emails are stored locally.
- **Sorting** results by score or property name.

---

## Architecture

<p align="center">
  <img src="assets/architecture.png" alt="Architecture diagram" width="800"/>
</p>

What happens to each lead (`scripts/run_batch.py` → `process_row`):

```
CSV row
  │
  ├─► Resolve ZIP code (CSV value, or geocode with OpenStreetMap Nominatim)
  ├─► Census demographics for the ZIP
  ├─► FeaturePipeline
  │     ├─ Firecrawl search + scrape → Apartments.com, Zillow
  │     ├─ Gemini 2.5 Flash-Lite → structured features (validated by Pydantic)
  │     └─ Gemini 2.5 Flash + Google Search → buying triggers
  ├─► domain/scoring.py → score, bucket, breakdown, reasons
  └─► Gemini 2.5 Flash → outreach email
        │
        └─► cached in data/lead_cache.json  (scrapes in data/scrape_cache.json)
```

---

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| LLM | Google Gemini 2.5 Flash / Flash-Lite via LangChain (`langchain-google-genai`) |
| Web scraping | Firecrawl |
| Geocoding | geopy (OpenStreetMap Nominatim) |
| Demographics | U.S. Census Bureau APIs (2020 Census, 2024 American Community Survey) |
| Validation | Pydantic v2 |
| Data | pandas, local JSON caches |
| Config | python-dotenv |

---

## How leads are scored

All rules are defined in [`domain/scoring.py`](domain/scoring.py).

**Final score** (`lead_score`):

| Component | Weight | What it measures |
|---|---|---|
| Account fit | 35% | Unit count, manager portfolio size, property type |
| Operational complexity | 25% | Vacancy pressure, floorplans, detected PMS vendor, review volume × complaint rate |
| Buying triggers | 20% | Recent ownership change, lease-up, hiring, expansion, tech change (more recent scores higher) |
| Market context | 10% | Census population, employment, occupancy |
| Data confidence | 10% | How many lookups succeeded |

**Priority bucket** (`priority_bucket`):

| Condition | Bucket |
|---|---|
| Data confidence < 0.4 | Needs Review |
| Score ≥ 0.80 | High |
| Score ≥ 0.60 | Medium |
| Score ≥ 0.40 | Low |
| Otherwise | Needs Review |

Scores are recomputed from cached features on every run, so changing the weights takes effect without new API calls.

---

## Getting started

### Requirements

- Python 3.10+
- A Google Gemini API key and a Firecrawl API key

### 1. Clone and install

```bash
git clone https://github.com/pchourasia1/LeadIntel.git
cd LeadIntel

python -m venv .venv
source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
                                 # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Add your API keys

Create a `.env` file in the project root (it is git-ignored):

```env
GOOGLE_API_KEY=your-gemini-key
FIRECRAWL_API_KEY=your-firecrawl-key
```

| Key | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) → **Create API key** |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://www.firecrawl.dev) → Dashboard → **API Keys** |

The Census APIs need no key.

### 3. Run the app

From the project root:

```bash
streamlit run app/main.py
```

Then in the browser:

1. Review the leads table (pre-loaded from `data/sample_input.csv`) or add a lead from the sidebar.
2. Tick **Run** for leads to process (uses the cache), or **Refresh** to force fresh LLM calls (scrapes stay cached).
3. Click **Generate Lead** and review the scored lead cards and draft emails.

### Run without the UI

```bash
python -m scripts.run_batch
```

Prints a score for every lead in `data/sample_input.csv`.

---

## Input format

`data/sample_input.csv`:

| Column | Required | Notes |
|---|---|---|
| Name | ✓ | Lead's name |
| Email | ✓ | Lead's email |
| Property Name | | Used for search; strongly recommended |
| Property Address | ✓ | Street address |
| City | ✓ | |
| State | ✓ | |
| Zipcode | | 5 digits; geocoded from the address if blank |
| Country | ✓ | e.g. `US` |

---

## Project structure

```
LeadIntel/
├── app/main.py                     # Streamlit UI
├── scripts/
│   ├── run_batch.py                # Per-lead pipeline (process_row, redraft_email, run_batch)
│   └── misc.py                     # CSV schema enforcement
├── services/
│   ├── feature_pipeline.py         # Orchestrates enrichment + Gemini calls
│   ├── enrichment/                 # Apartments.com, Zillow, account fit
│   ├── email_drafter.py            # Outreach email generation
│   ├── prompts/buying_trigger.md   # Grounded-search prompt
│   ├── llm_utils.py                # JSON extraction from LLM replies
│   └── markdown_utils.py           # Section slicing for scraped pages
├── clients/
│   ├── firecrawl_client.py         # Search + scrape
│   ├── census_client.py            # Census APIs
│   ├── scrape_cache.py             # Page cache  → data/scrape_cache.json
│   └── lead_cache.py               # Feature/email cache → data/lead_cache.json
├── domain/scoring.py               # Scoring model (pure Python, no I/O)
├── schemas/pydantic_schemas.py     # LLM output schemas
├── data/                           # Sample input + caches
└── assets/                         # README media
```

---

## Notes

- **Costs:** each new property uses several Firecrawl credits and Gemini calls; cached properties cost nothing to re-run.
- **Clearing the cache:** delete `data/lead_cache.json` and/or `data/scrape_cache.json` to start fresh.
- **Models** are set in `services/feature_pipeline.py`; update them there if Google retires a Gemini version.
- Scraping is for research purposes; respect the terms of service of the sites involved.
