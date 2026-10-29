"""
Load the raw Olist CSVs, clean them with pandas, and build a star schema in DuckDB.

Steps
1. Extract  - read the 8 raw CSV files from data/raw/
2. Transform - fix types, remove duplicates, fill gaps (see clean_* functions)
3. Load      - write cleaned staging tables (stg_*) into olist.duckdb,
               then run sql/schema.sql to build the dimension and fact tables

Run from the repo root:
    python etl/load.py
"""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB_PATH = ROOT / "olist.duckdb"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"

RAW_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


# ---------------------------------------------------------------- extract
def extract() -> dict[str, pd.DataFrame]:
    missing = [f for f in RAW_FILES.values() if not (RAW / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing files in {RAW}: {missing}. "
            "Download the dataset from Kaggle (see README) and unzip it into data/raw/."
        )
    return {name: pd.read_csv(RAW / f) for name, f in RAW_FILES.items()}


# ---------------------------------------------------------------- transform
def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    # All timestamp columns arrive as text; parse them so date math works.
    ts_cols = [c for c in df.columns if c.startswith("order_") and c not in ("order_id", "order_status")]
    for col in ts_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    # Missing delivery dates are expected for orders that were never delivered
    # (canceled, unavailable, still in transit), so they stay NULL.
    return df


def clean_order_items(df: pd.DataFrame) -> pd.DataFrame:
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    return df


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    # Data quality issue: some orders have more than one review, and some
    # review_ids repeat across orders. For "one score per order" analysis we
    # keep the most recently answered review for each order.
    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    df = (
        df.sort_values("review_answer_timestamp")
        .drop_duplicates(subset="order_id", keep="last")
        [["order_id", "review_score", "review_creation_date", "review_comment_message"]]
    )
    df["has_comment"] = df["review_comment_message"].notna()
    return df.drop(columns="review_comment_message")


def clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    # An order can be paid in several parts (e.g. voucher + credit card).
    # Roll up to one row per order: total paid and the main payment type.
    main_type = (
        df.sort_values("payment_value", ascending=False)
        .drop_duplicates("order_id")[["order_id", "payment_type"]]
    )
    totals = df.groupby("order_id", as_index=False).agg(
        payment_value=("payment_value", "sum"),
        payment_installments=("payment_installments", "max"),
    )
    return totals.merge(main_type, on="order_id", how="left")


def clean_products(df: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    # The source misspells "length" as "lenght"; fix the column names.
    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    # Translate Portuguese category names to English; 610 products have no category.
    df = df.merge(translation, on="product_category_name", how="left")
    df["category"] = (
        df["product_category_name_english"]
        .fillna(df["product_category_name"])   # a few categories have no translation
        .fillna("unknown")
    )
    return df.drop(columns=["product_category_name", "product_category_name_english"])


def transform(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {
        "stg_orders": clean_orders(raw["orders"]),
        "stg_order_items": clean_order_items(raw["order_items"]),
        "stg_reviews": clean_reviews(raw["reviews"]),
        "stg_payments": clean_payments(raw["payments"]),
        "stg_customers": raw["customers"],
        "stg_sellers": raw["sellers"],
        "stg_products": clean_products(raw["products"], raw["category_translation"]),
    }


# ---------------------------------------------------------------- load
def load(staging: dict[str, pd.DataFrame]) -> None:
    con = duckdb.connect(str(DB_PATH))
    for name, df in staging.items():
        # DuckDB can read a pandas DataFrame directly by its Python variable name.
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
        print(f"  {name:<18} {len(df):>8,} rows")

    con.execute(SCHEMA_SQL.read_text())
    for table in ["dim_customer", "dim_seller", "dim_product", "dim_date", "fact_orders", "fact_order_items"]:
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<18} {n:>8,} rows")
    con.close()


if __name__ == "__main__":
    print("Extracting raw CSVs...")
    raw = extract()
    print("Cleaning and loading staging tables...")
    staging = transform(raw)
    load(staging)
    print(f"Done. Database written to {DB_PATH.name}")
