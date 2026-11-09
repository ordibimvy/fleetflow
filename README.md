# fleetflow

[![CI](https://github.com/ordibimvy/fleetflow/actions/workflows/ci.yml/badge.svg)](https://github.com/ordibimvy/fleetflow/actions/workflows/ci.yml)

A containerized data pipeline for fleet fuel-card transactions, wrapped in the tooling a platform team owns: automated data-quality checks, CI/CD, a reusable workflow template, observability, and infrastructure as code.

Raw transactions land in **bronze**, are cleaned into **silver**, and roll up into **gold** daily spend per fleet. Every push is linted, run end to end against a fresh Postgres, checked by seven data-quality tests, and packaged as a versioned Docker image.

## Architecture

```mermaid
flowchart LR
    subgraph local["Local development"]
        gen["generate.py<br/>5,040 synthetic transactions<br/>with injected dirty data"]
        subgraph pg["Postgres 16 (Docker)"]
            bronze["bronze.transactions<br/>raw, all TEXT"]
            silver["silver.transactions<br/>typed, deduped, validated"]
            gold["gold.daily_fleet_spend<br/>spend per fleet per day"]
            ops["ops.run_metrics<br/>one row per run"]
        end
        tests["pytest<br/>7 data-quality checks"]
        tf["Terraform<br/>Docker provider"]
    end

    gen -->|"COPY"| bronze
    bronze -->|"clean + reject"| silver
    silver -->|"aggregate"| gold
    silver -.->|"counts + duration"| ops
    tests -.->|"query"| pg
    tf -.->|"provisions"| pg
```

### CI/CD on every push

```mermaid
flowchart LR
    push["git push"] --> lint["lint<br/>ruff"]
    lint --> checks["pipeline-and-data-checks<br/>reusable workflow:<br/>Postgres service, run pipeline,<br/>run 7 tests, write summary"]
    checks --> build["build-image<br/>docker build"]
    build -->|"main branch only"| ghcr["GitHub Container Registry<br/>tagged with commit SHA"]
```

A failing data check stops the run before an image is built, so bad transformation logic never gets packaged.

## The medallion layers

| Layer | What it holds | Why |
|---|---|---|
| **Bronze** | Raw CSV rows, every column stored as `TEXT` | Loads never fail on bad values, and the raw copy can always be replayed |
| **Silver** | Typed, trimmed, deduplicated rows that pass business rules | One trustworthy row per transaction |
| **Gold** | Daily transaction count, gallons, spend, and weighted average price per fleet | Answers a business question directly |

### Dirty data, on purpose

The generator injects the same kinds of problems real feeds have:

| Problem | Rows | How silver handles it |
|---|---|---|
| Blank fleet IDs (spaces, not nulls) | 50 | Rejected: `NULLIF(TRIM(fleet_id), '') IS NOT NULL` |
| Negative amounts | 25 | Rejected: `amount_usd > 0` |
| Exact duplicate transactions | 40 | Removed: `DISTINCT ON (txn_id)` |
| Messy fuel types like `  DIESEL ` | 100 | Cleaned, not rejected: `LOWER(TRIM(fuel_type))` |

A typical run: **5,040 bronze → 4,925 silver (115 rejected) → 748 gold rows.**

## Data-quality checks

`tests/test_quality.py` runs after the pipeline, locally and in CI.

| Test | Catches |
|---|---|
| `test_gold_is_not_empty` | A pipeline that ran but produced nothing |
| `test_silver_has_no_duplicate_transactions` | Broken deduplication |
| `test_silver_has_no_missing_fleet_ids` | Rows that slipped past the fleet rule |
| `test_silver_has_no_negative_amounts` | Rows that slipped past the amount rule |
| `test_fuel_types_are_clean` | Casing or whitespace leaking into silver |
| `test_gold_reconciles_with_silver` | Money lost or duplicated during aggregation |
| `test_reject_rate_is_reasonable` | An upstream change: fails if more than 5% of rows are rejected |

The last two matter most. Reconciliation proves no money is lost between layers. The reject-rate threshold catches upstream changes that every other test would miss, because silver still looks clean while silently dropping data.

These checks were verified by breaking deduplication on purpose in a pull request: CI failed on `test_silver_has_no_duplicate_transactions` and blocked the change.

## Observability

- **Structured JSON logs**, one object per line, all sharing a `run_id` so a single run can be traced end to end
- **`ops.run_metrics`** records bronze, silver, rejected, and gold counts plus duration for every run, giving a baseline to compare new runs against
- **CI job summary** renders the metrics table on each run's page

```bash
python -m pipeline.run | jq 'select(.msg == "built silver")'
```

## Run it locally

Requires Docker Desktop and Python 3.12 or newer.

**Option 1: everything in containers**

```bash
docker compose up --build pipeline
docker compose run --rm pipeline pytest -v tests
docker compose down
```

**Option 2: Python on your machine, Postgres in Docker**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d --wait db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fleetflow python -m pipeline.run
pytest -v tests
```

Inside Compose, the database host is the service name `db`. From your own machine, it's `localhost`.

## Infrastructure as code

`infra/` provisions a Postgres container, network, and image with Terraform's Docker provider. This runs the real Terraform workflow locally at no cloud cost. Moving to AWS means changing the provider and resource types, not the workflow.

```bash
cd infra
terraform init
terraform plan      # preview: 3 to add
terraform apply
terraform destroy
```

Deleting the container by hand and re-running `terraform plan` shows the drift (`1 to add`), and `apply` restores it.

## Project structure

```
fleetflow/
├── .github/workflows/
│   ├── ci.yml                       # lint → data checks → build and push image
│   └── data-checks-reusable.yml     # reusable workflow other repos can call
├── infra/
│   ├── main.tf                      # network, image, container
│   ├── variables.tf
│   └── output.tf
├── pipeline/
│   ├── generate.py                  # synthetic transactions with dirty data
│   ├── run.py                       # orchestrates layers, logs, metrics
│   └── sql/
│       ├── 01_bronze.sql
│       ├── 02_silver.sql
│       └── 03_gold.sql
├── tests/
│   └── test_quality.py              # 7 data-quality checks
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml                   # ruff config
└── requirements.txt
```

## Known limitations

- `ops.run_metrics.finished_at` uses `DEFAULT now()`, which returns the **transaction start** time in Postgres, not the insert time. It's closer to a start time than a finish time. The fix is `clock_timestamp()` or renaming the column.
- The Compose database has no volume, so run history resets when the container is recreated.
- The generator uses a fixed seed, so row counts are identical every run. That keeps tests repeatable, but real data would vary.

## Roadmap

- [ ] Refactor Terraform into a reusable module and provision dev and staging from one definition
- [ ] Add a volume so run history persists
- [ ] Update GitHub Actions to their latest major versions
- [ ] Run the pipeline as a Kubernetes Job on a local `kind` cluster
- [ ] Rewrite silver and gold as dbt models
- [ ] Add a read-only AI agent tool that answers questions over the gold table

## Tech

Python 3.12 · PostgreSQL 16 · psycopg 3 · pytest · ruff · Docker · Docker Compose · GitHub Actions · GitHub Container Registry · Terraform
