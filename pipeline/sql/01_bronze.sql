CREATE SCHEMA IF NOT EXISTS bronze;
DROP TABLE IF EXISTS bronze.transactions;
CREATE TABLE bronze.transactions (
    txn_id         TEXT,
    fleet_id       TEXT,
    card_id        TEXT,
    txn_ts         TEXT,
    merchant_state TEXT,
    fuel_type      TEXT,
    gallons        TEXT,
    amount_usd     TEXT,
    loaded_at      TIMESTAMPTZ DEFAULT now()
);