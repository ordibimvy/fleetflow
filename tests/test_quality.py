"""Data quality checks. Run these AFTER the pipeline. Each test fails loudly on bad data."""
import os

import psycopg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleetflow")


@pytest.fixture(scope="module")
def cur():
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as c:
        yield c


def one(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def test_gold_is_not_empty(cur):
    assert one(cur, "SELECT COUNT(*) FROM gold.daily_fleet_spend") > 0


def test_silver_has_no_duplicate_transactions(cur):
    dupes = one(cur, "SELECT COUNT(*) - COUNT(DISTINCT txn_id) FROM silver.transactions")
    assert dupes == 0, f"{dupes} duplicate txn_ids in silver"


def test_silver_has_no_missing_fleet_ids(cur):
    assert one(cur, "SELECT COUNT(*) FROM silver.transactions WHERE fleet_id IS NULL") == 0


def test_silver_has_no_negative_amounts(cur):
    assert one(cur, "SELECT COUNT(*) FROM silver.transactions WHERE amount_usd <= 0") == 0


def test_fuel_types_are_clean(cur):
    cur.execute("SELECT DISTINCT fuel_type FROM silver.transactions ORDER BY 1")
    assert [r[0] for r in cur.fetchall()] == ["diesel", "premium", "unleaded"]


def test_gold_reconciles_with_silver(cur):
    silver_total = one(cur, "SELECT SUM(amount_usd) FROM silver.transactions")
    gold_total = one(cur, "SELECT SUM(total_spend) FROM gold.daily_fleet_spend")
    assert silver_total == gold_total


def test_reject_rate_is_reasonable(cur):
    rate = one(
        cur,
        "SELECT rejected_rows::NUMERIC / bronze_rows FROM ops.run_metrics ORDER BY finished_at DESC LIMIT 1",
    )
    assert rate < 0.05, f"reject rate {rate:.1%} is above 5%"