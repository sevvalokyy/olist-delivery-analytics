"""
Run every query in sql/analysis/ against olist.duckdb, save each result to
results/<name>.csv and print it.

Run from the repo root after etl/load.py:
    python run_analyses.py
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
QUERIES = sorted((ROOT / "sql" / "analysis").glob("*.sql"))
RESULTS = ROOT / "results"


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(ROOT / "olist.duckdb"), read_only=True)
    for path in QUERIES:
        df = con.execute(path.read_text()).df()
        df.to_csv(RESULTS / f"{path.stem}.csv", index=False)
        print(f"\n=== {path.stem} ===")
        print(df.to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
