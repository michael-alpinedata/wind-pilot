# 🪁 Wind-Pilot — Lake Bourget Wind Analytics & Wing Foil Gear Advisor

A full-stack data pipeline, analytics dashboard, and LLM-powered Wing Foil
Gear Advisor built on historical wind data from the **Pioupiou 2176
anemometer** (Baie de Mémard, Lac du Bourget) — built with **dlt**, **dbt**,
**Postgres (Neon)**, **Streamlit**, and (in progress) **RAG on pgvector**.

Live dashboard: https://wind-pilot.streamlit.app/

This started as a practical question — *"when can I actually sail this
spot, with the gear I have?"* — and grew into an LLM Zoomcamp capstone
project: a proper incremental pipeline feeding an analytics dashboard, plus
a retrieval-augmented gear advisor trained on manufacturer size charts.

---

## 🏗️ Architecture

```
OpenWindMap / Pioupiou API
        │
        ▼
dlt pipeline (incremental extraction, schema evolution detection)
        │
        ▼
PostgreSQL (Neon Cloud DB) — raw layer
        │
        ▼
dbt (staging ➔ intermediate ➔ marts)
   (source freshness checks, data quality tests)
        │
        ▼
Streamlit Dashboard + RAG Gear Advisor (LLM Zoomcamp capstone)
```

Runs hourly via a scheduled GitHub Action (`.github/workflows/pipeline.yml`)
— see [Automation](#-automation-github-actions) below.

### Why this stack

| Layer | Tool | Why |
|---|---|---|
| Extraction | [dlt](https://dlthub.com/) | Incremental loading, automatic schema evolution detection, minimal boilerplate |
| Warehouse | [Neon](https://neon.tech/) (serverless Postgres) | Free tier, standard Postgres wire protocol, `pgvector` support for the RAG layer |
| Transformation | [dbt](https://www.getdbt.com/) | staging/intermediate/marts layering, source freshness + data quality tests |
| Orchestration | GitHub Actions (cron) | No extra infra to run/pay for at this scale |
| Dashboard | [Streamlit](https://streamlit.io/) + Plotly | Fast to iterate, reads directly from the marts, free hosting on Community Cloud |
| Dependency management | [uv](https://docs.astral.sh/uv/) | Single `pyproject.toml`, extras split by concern so each part only installs what it needs |

---

## 🚀 Key Features

* **Incremental Data Pipeline (`dlt`)**: automated batch ingestion from the
  Pioupiou API directly into Neon PostgreSQL, with automatic resumption
  from the last loaded point and schema-drift detection.
* **Data Transformation (`dbt`)**:
  * Cleaned staging layer with typing and range validation
  * Local timezone conversion (UTC → `Europe/Paris`)
  * Enriched metrics: 16-point wind direction rose, day/night thermal wind
    slots, km/h ↔ knots conversion centralized in one place
  * Production marts for daily time series, hourly profiles, monthly
    seasonality, and wind rose data
  * `dbt source freshness` + column-level tests so a silent API failure
    shows up as a failed CI run instead of a stale, unnoticed dashboard
* **Interactive Analytics Dashboard (`Streamlit`)**:
  * **Unit switcher**: toggle between knots (`kn`), `km/h`, and `m/s` with
    dynamic chart conversion
  * **Daily & seasonal analytics**: date range slider, day/night slot
    filters, monthly navigable-wind percentages
  * **Hourly thermal profile**: hourly mean/median/**P90** to pinpoint when
    the local thermal wind ("La Traverse") typically picks up
  * **Standard compass wind rose**: 16-sector polar plot, true geographic
    orientation (North up, East right)
* **🤖 AI Wing Foil Gear Advisor (RAG capstone project)**:
  * Recommends wing size (m²), front foil surface (cm²), and board volume
    (L) based on rider weight, experience level, and forecast wind speed
  * Retrieval-augmented generation over manufacturer size-guide datasheets
    (Gong, F-One, Duotone, etc.), indexed in Neon `pgvector`
  * Built as the capstone project for
    [LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp)

---

## 🛠️ Repository Structure

```
wind-pilot/
├── dashboard/
│   └── streamlit_app.py      # Streamlit dashboard + RAG advisor UI
├── dbt_project/               # dbt transformations
│   ├── dbt_project.yml
│   ├── packages.yml
│   ├── profiles.yml           # env_var()-based, safe to commit
│   ├── profiles.yml.example
│   └── models/
│       ├── staging/           # raw data casting & quality tests
│       ├── intermediate/      # local time conversion, unit conversion, 16-point directions
│       └── marts/             # aggregated tables consumed by the dashboard
├── dlt_pipeline/               # ingestion
│   ├── pipeline.py             # dlt incremental pipeline
│   ├── utils/                  # DB connectivity & validation helpers
│   └── .dlt/secrets.toml.example
├── .github/workflows/
│   └── pipeline.yml            # hourly cron: dlt run → dbt build
├── pyproject.toml
└── README.md
```

---

## ⚡ Quickstart & Local Setup

### 1. Requirements & Dependencies

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

Dependencies are split into extras by concern, so you only install what a
given part of the pipeline needs:

```bash
git clone https://github.com/your-username/wind-pilot.git
cd wind-pilot

uv sync --extra dlt         # for dlt_pipeline/
uv sync --extra dbt         # for dbt_project/
uv sync --extra streamlit   # for dashboard/
uv sync --all-extras        # everything at once (convenient for local dev)
```

### 2. Database & Credentials Configuration

#### Local environment file (`.env`)

Create a `.env` at the repo root:

```env
NEON_HOST=your-neon-host.tech
NEON_DB=neondb
NEON_USER=neondb_owner
NEON_PASSWORD=your-password
NEON_SCHEMA=dbt_dev_marts
```

Use the **direct** Neon endpoint (no `-pooler` suffix) — PgBouncer's
transaction pooling mode doesn't support the session-level `search_path`
parameter dlt needs for schema evolution, and will fail the connection.

#### dlt (`dlt_pipeline/.dlt/secrets.toml`)

```bash
cp dlt_pipeline/.dlt/secrets.toml.example dlt_pipeline/.dlt/secrets.toml
# fill in the same Neon credentials as above
```

#### Streamlit Cloud / local Streamlit secrets (`.streamlit/secrets.toml`)

```toml
NEON_HOST = "your-neon-host.tech"
NEON_DB = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "your-password"
NEON_SCHEMA = "dbt_dev_marts"
```

#### dbt (`dbt_project/profiles.yml`)

Already committed and safe as-is — it reads the same values via
`env_var()`, so just export them in your shell (or rely on `.env` if your
shell loads it automatically):

```bash
export NEON_HOST=... NEON_DB=... NEON_USER=... NEON_PASSWORD=...
```

### 3. Data Ingestion (`dlt`)

```bash
cd dlt_pipeline
uv run python pipeline.py --backfill 2025-01-01   # initial historical backfill
uv run python pipeline.py                          # subsequent runs: automatic incremental
```

### 4. Data Transformations & Quality (`dbt`)

```bash
cd dbt_project
uv run dbt deps
uv run dbt source freshness
uv run dbt build
```

`dbt build` runs models and tests in dependency order — if a staging-level
quality test fails (e.g. wind values out of range), downstream marts aren't
rebuilt on top of corrupted data.

### 5. Launching the Dashboard

```bash
uv run streamlit run dashboard/streamlit_app.py
```

---

## 🤖 Automation (GitHub Actions)

`.github/workflows/pipeline.yml` runs every hour (`5 * * * *`) and chains
`pipeline.py` → `dbt build`. It needs four repo secrets under **Settings →
Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `NEON_HOST` | direct Neon endpoint (no `-pooler`) |
| `NEON_DB` | database name |
| `NEON_USER` | e.g. `neondb_owner` |
| `NEON_PASSWORD` | the password |

No credentials are committed anywhere — everything flows through these
secrets via dlt's env-var config convention
(`DESTINATION__POSTGRES__CREDENTIALS__*`) and dbt's `env_var()` in
`profiles.yml`.

Manual runs are available from the Actions tab (`workflow_dispatch`), with
an optional input to trigger a backfill from a specific date instead of the
normal incremental run.

---

## 📊 Data Models Overview

| Model | Materialization | Description |
| --- | --- | --- |
| `stg_pioupiou_measurements` | View | Cleaned raw measurements with standard timestamp casting and range validations |
| `int_measurements_enriched` | View | Local time parsing (`Europe/Paris`), day/night slot categorization, 16-point compass directions, knots conversion |
| `mart_wind_by_day` | Table | Daily aggregations (mean, median, P90, max gust), split by day/night slot |
| `mart_wind_by_hour` | Table | Hourly aggregated statistics (0–23h) to surface thermal wind patterns |
| `mart_wind_by_month` | Table | Monthly averages and % of time above configurable navigable-wind thresholds |
| `mart_wind_rose` | Table | Directional distribution by wind speed bracket, for the polar plot |

---

## 🎯 LLM Zoomcamp Capstone Roadmap

* [x] Incremental data pipeline (dlt → Postgres) with schema evolution handling
* [x] dbt transformation layer with source freshness + data quality tests
* [x] Streamlit analytics dashboard (time series, hourly profile, seasonality, wind rose, unit switcher)
* [x] Streamlit UI inputs for rider weight, skill level, forecast wind speed
* [ ] Document ingestion & chunking: parsing PDF/HTML size guides from major brands (Gong, F-One, Duotone, Takoon)
* [ ] Vector store setup on Neon `pgvector`
* [ ] Hybrid search & reranking (keyword + vector similarity)
* [ ] Evaluation & monitoring (Ragas evaluation suite, execution tracking)

---

## Known limitations / things to recalibrate

- The day/night split (10:00–19:00 local) is an initial approximation of
  the thermal wind window — worth revisiting once more seasons of data are
  in.
- The default navigable-wind thresholds are calibrated for one specific
  gear setup (inflatable board, 5m² wing, XL front foil, ~75 kg rider) —
  not a general-purpose threshold. The gear advisor is meant to eventually
  replace this hardcoded assumption with a per-rider recommendation.
- Station 2176 has only been active since April 2026, so winter/spring
  seasonal patterns aren't in the data yet.

---

## 📜 Data License & Attribution

Wind measurement data provided by the
**[OpenWindMap](https://www.openwindmap.org)** community sensor network —
anemometer **Pioupiou 2176** (Baie de Mémard, Lac du Bourget), via their
[archive API](https://developers.pioupiou.fr/api/archive/). See their
[data licensing terms](https://developers.pioupiou.fr/data-licensing) for
reuse conditions.
