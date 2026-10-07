"""Create a fake fleet-card transactions CSV, with some dirty rows on purpose."""
import csv
import random
from datetime import datetime, timedelta

FUELS = ["diesel", "unleaded", "premium"]
STATES = ["ME", "NH", "MA", "CO", "TX"]


def make_rows(n=5000, seed=42):
    rng = random.Random(seed)
    start = datetime(2026, 9, 1)
    rows = []
    for i in range(n):
        fuel = rng.choice(FUELS)
        gallons = round(rng.uniform(5, 40), 2)
        price = {"diesel": 3.9, "unleaded": 3.3, "premium": 3.9}[fuel] + rng.uniform(-0.3, 0.3)
        rows.append({
            "txn_id": f"T{i:06d}",
            "fleet_id": f"F{rng.randint(1, 25):03d}",
            "card_id": f"C{rng.randint(1, 300):04d}",
            "txn_ts": (start + timedelta(minutes=rng.randint(0, 30 * 24 * 60))).isoformat(),
            "merchant_state": rng.choice(STATES),
            "fuel_type": fuel,
            "gallons": str(gallons),
            "amount_usd": str(round(gallons * price, 2)),
        })
    # Dirty data, like real life
    for r in rng.sample(rows, 50):
        r["fleet_id"] = "   "          # blank fleet id
    for r in rng.sample(rows, 25):
        r["amount_usd"] = "-" + r["amount_usd"]  # negative amount
    for r in rng.sample(rows, 100):
        r["fuel_type"] = f"  {r['fuel_type'].upper()} "  # messy casing and spaces
    rows += [dict(r) for r in rng.sample(rows, 40)]       # duplicate transactions
    return rows


def write_csv(path="data/transactions.csv", n=5000):
    rows = make_rows(n)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {write_csv()} rows")