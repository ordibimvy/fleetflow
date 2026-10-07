"""Run the pipeline: generate -> bronze -> silver -> gold, and record run metrics."""
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import psycopg

from pipeline.generate import write_csv

SQL_DIR = Path(__file__).parent / "sql"
CSV_PATH = Path("data/transactions.csv")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleetflow")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {"level": record.levelname, "msg": record.getMessage(), "time": self.formatTime(record)}
        entry.update(getattr(record, "extra_fields", {}))
        return json.dumps(entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
log = logging.getLogger("fleetflow")
log.addHandler(handler)
log.setLevel(logging.INFO)


def info(msg, **fields):
    log.info(msg, extra={"extra_fields": fields})


def count(cur, table):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def main():
    run_id = str(uuid.uuid4())[:8]
    started = time.time()
    CSV_PATH.parent.mkdir(exist_ok=True)
    rows = write_csv(str(CSV_PATH))
    info("generated csv", run_id=run_id, rows=rows)

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute((SQL_DIR / "01_bronze.sql").read_text())
        cols = "txn_id, fleet_id, card_id, txn_ts, merchant_state, fuel_type, gallons, amount_usd"
        with open(CSV_PATH) as f, cur.copy(f"COPY bronze.transactions ({cols}) FROM STDIN WITH CSV HEADER") as copy:
            copy.write(f.read())
        bronze = count(cur, "bronze.transactions")
        info("loaded bronze", run_id=run_id, rows=bronze)

        cur.execute((SQL_DIR / "02_silver.sql").read_text())
        silver = count(cur, "silver.transactions")
        info("built silver", run_id=run_id, rows=silver, rejected=bronze - silver)

        cur.execute((SQL_DIR / "03_gold.sql").read_text())
        gold = count(cur, "gold.daily_fleet_spend")
        info("built gold", run_id=run_id, rows=gold)

        duration = round(time.time() - started, 2)
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS ops;
            CREATE TABLE IF NOT EXISTS ops.run_metrics (
                run_id TEXT PRIMARY KEY, finished_at TIMESTAMPTZ DEFAULT now(),
                bronze_rows INT, silver_rows INT, rejected_rows INT, gold_rows INT, duration_s NUMERIC
            )""")
        cur.execute(
            "INSERT INTO ops.run_metrics (run_id, bronze_rows, silver_rows, rejected_rows, gold_rows, duration_s)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (run_id, bronze, silver, bronze - silver, gold, duration),
        )
    info("run finished", run_id=run_id, duration_s=duration)


if __name__ == "__main__":
    main()