# 🪁 Wind-Pilot — Lake Bourget Wind Analytics & Wing Foil Gear Advisor

A full-stack data pipeline, analytics dashboard, and LLM-powered Wing Foil Gear Advisor based on historical wind data from the **Pioupiou 2176 anemometer** (Baie de Mémard, Lac du Bourget).

---

## 🏗️ Architecture


```

OpenWindMap / Pioupiou API
│
▼
dlt pipeline (Incremental extraction)
│
▼
PostgreSQL (Neon Cloud DB)
│
▼
dbt (Staging ➔ Intermediate ➔ Marts)
│
▼
Streamlit Dashboard + RAG Gear Advisor (LLM Zoomcamp Capstone)

```

---

## 🚀 Key Features

* **Incremental Data Pipeline (`dlt`)**: Automated batch ingestion from the Pioupiou API directly into Neon PostgreSQL.
* **Data Transformation (`dbt`)**:
  * Cleaned staging layers and local timezone conversions (UTC to `Europe/Paris`).
  * Enriched metrics (16-point wind direction rose, day/night thermal wind slots).
  * Production data marts for daily time series, hourly profiles, monthly seasonality, and wind roses.
* **Interactive Analytics Dashboard (`Streamlit`)**:
  * **Unit Switcher**: Toggle between Knots (`kn`), `km/h`, and `m/s` with dynamic chart conversions.
  * **Daily & Seasonal Analytics**: Interactive date range slider, day/night slot filters, and monthly navigable wind percentages.
  * **Hourly Thermal Profile**: Hourly averages, medians, and **P90 percentile** tracking to pinpoint local thermal wind rises (*La Traverse*).
  * **Standard Compass Wind Rose**: 16-sector polar plot aligned with true geographical directions (North at top, East at right).
* **🤖 AI Wing Foil Gear Advisor (RAG Project)**:
  * Recommends optimal wing size ($m^2$), front wing foil surface ($cm^2$), and board volume ($L$) based on rider weight, experience level, and forecast wind speed.
  * Designed as a Capstone Project for **LLM Zoomcamp** using Retrieval-Augmented Generation (RAG) on gear manufacturer datasheets (Gong, F-One, Duotone, etc.) stored in Neon `pgvector`.

---

## 🛠️ Repository Structure


```

wind-pilot/
├── dashboard/
│   └── streamlit_app.py      # Streamlit v2.0 Dashboard & RAG UI
├── dbt_project/              # dbt transformations
│   ├── dbt_project.yml
│   ├── packages.yml
│   ├── profiles.yml.example
│   └── models/
│       ├── staging/          # Raw data casting & quality tests
│       ├── intermediate/     # Local time conversion & 16-point directions
│       └── marts/            # Aggregated tables for Streamlit analytics
├── dlt_pipeline/             # Ingestion scripts
│   ├── pipeline.py           # dlt incremental pipeline
│   └── utils/                # DB connectivity & validation tools
├── pyproject.toml
└── README.md

```

---

## ⚡ Quickstart & Local Setup

### 1. Requirements & Dependencies

Make sure you have Python 3.10+ installed. You can manage dependencies with `uv` or standard `pip`:

```bash
git clone [https://github.com/your-username/wind-pilot.git](https://github.com/your-username/wind-pilot.git)
cd wind-pilot

uv sync 
# or
pip install streamlit plotly sqlalchemy psycopg2-binary pandas python-dotenv dlt dbt-postgres

```

---

### 2. Database & Credentials Configuration

Copy the example configuration files and fill in your Neon PostgreSQL database credentials.

#### Local Environment File (`.env`)

Create a `.env` file at the root directory:

```env
NEON_HOST=your-neon-host.tech
NEON_DB=neondb
NEON_USER=neondb_owner
NEON_PASSWORD=your-password
NEON_SCHEMA=dbt_dev_marts

```

#### Streamlit Cloud / `.streamlit/secrets.toml`

For Streamlit Cloud deployments or local Streamlit secret testing, populate `.streamlit/secrets.toml`:

```toml
NEON_HOST = "your-neon-host.tech"
NEON_DB = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "your-password"
NEON_SCHEMA = "dbt_dev_marts"

```

---

### 3. Data Ingestion (`dlt`)

Run a historical backfill or perform incremental extractions from the Pioupiou API:

```bash
cd dlt_pipeline
uv run python pipeline.py --backfill 2025-01-01   # Initial historical backfill
uv run python pipeline.py                          # Subsequent incremental runs

```

---

### 4. Data Transformations & Quality (`dbt`)

Run tests and build data marts in Neon Postgres:

```bash
cd dbt_project
uv run dbt deps
uv run dbt source freshness
uv run dbt build

```

---

### 5. Launching the Dashboard

Start the Streamlit application locally:

```bash
uv run streamlit run dashboard/streamlit_app.py

```

---

## 📊 Data Models Overview

| Model Name | Materialization | Description |
| --- | --- | --- |
| `stg_pioupiou_measurements` | View | Cleaned raw measurements with standard timestamp casting and range validations. |
| `int_measurements_enriched` | View | Local time parsing (`Europe/Paris`), day/night time-slot categorization, and 16-point compass directions. |
| `mart_wind_by_day` | Table | Daily aggregations (mean, median, P90, max gust) split by day/night slots. |
| `mart_wind_by_hour` | Table | Hourly aggregated statistics (0–23h) to analyze thermal wind patterns. |
| `mart_wind_range` | Table | Monthly averages and percentage of time above navigable wind thresholds. |
| `mart_wind_rose` | Table | Directional distributions grouped by wind speed brackets for polar plotting. |

---

## 🎯 LLM Zoomcamp Capstone Roadmap

* [x] **Streamlit UI Integration**: Inputs for rider weight, skill level, and forecast wind speed.
* [ ] **Document Ingestion & Chunking**: Parsing PDF/HTML size guides from top brands (Gong, F-One, Duotone, Takoon).
* [ ] **Vector Database Setup**: Vector store initialization with Neon PostgreSQL `pgvector`.
* [ ] **Hybrid Search & Reranking**: Combining keyword matching with vector similarity and reranking models.
* [ ] **Evaluation & Monitoring**: Ragas evaluation suite and execution tracking.

---

## 📜 Data License & Attribution

Wind measurement data provided by the **[OpenWindMap](https://www.openwindmap.org)** community network — Anemometer **Pioupiou 2176** (Baie de Mémard / Lac du Bourget).
