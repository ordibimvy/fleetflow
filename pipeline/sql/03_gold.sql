CREATE SCHEMA IF NOT EXISTS gold;
DROP TABLE IF EXISTS gold.daily_fleet_spend;
CREATE TABLE gold.daily_fleet_spend AS
SELECT
    fleet_id,
    txn_ts::DATE                                   AS txn_date,
    COUNT(*)                                       AS txn_count,
    SUM(gallons)                                   AS total_gallons,
    SUM(amount_usd)                                AS total_spend,
    ROUND(SUM(amount_usd) / SUM(gallons), 3)       AS avg_price_per_gallon
FROM silver.transactions
GROUP BY fleet_id, txn_ts::DATE;

ALTER TABLE gold.daily_fleet_spend ADD PRIMARY KEY (fleet_id, txn_date);