CREATE SCHEMA IF NOT EXISTS silver;
DROP TABLE IF EXISTS silver.transactions;
CREATE TABLE silver.transactions AS
SELECT DISTINCT ON (txn_id)
    txn_id,
    NULLIF(TRIM(fleet_id), '')       AS fleet_id,
    card_id,
    txn_ts::TIMESTAMP                AS txn_ts,
    merchant_state,
    LOWER(TRIM(fuel_type))           AS fuel_type,
    gallons::NUMERIC(10, 2)          AS gallons,
    amount_usd::NUMERIC(12, 2)       AS amount_usd
FROM bronze.transactions
WHERE NULLIF(TRIM(fleet_id), '') IS NOT NULL
  AND amount_usd::NUMERIC > 0
ORDER BY txn_id;

ALTER TABLE silver.transactions ADD PRIMARY KEY (txn_id);