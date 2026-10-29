"""
Turn the CSVs in results/ into the PNG charts used in the README (images/).

Run from the repo root after run_analyses.py:
    python make_charts.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
IMAGES = ROOT / "images"

BLUE = "#2a78d6"     # on time / neutral series
RED = "#e34948"      # late
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"

plt.rcParams.update({
    "font.size": 10,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "figure.dpi": 150,
})


def title(ax, text, sub=None):
    ax.set_title(text, loc="left", fontsize=12, fontweight="bold", color=INK, pad=22 if sub else 10)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9, color=MUTED)


def review_by_delivery():
    df = pd.read_csv(RESULTS / "01_late_delivery_vs_review.csv")
    labels = df["delivery_bucket"].str[3:]
    colors = [RED if "late" in b else BLUE for b in df["delivery_bucket"]]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, df["avg_review"], color=colors, width=0.6)
    ax.bar_label(bars, labels=[f"{v:.2f}" for v in df["avg_review"]], padding=3, color=INK)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review score (1-5)")
    ax.grid(axis="x", visible=False)
    title(ax, "Late orders lose more than 2 stars on average",
          "Average review score by delivery time vs. the date promised at checkout (delivered orders)")
    fig.tight_layout()
    fig.savefig(IMAGES / "01_review_by_delivery.png")
    plt.close(fig)


def late_rate_by_month():
    df = pd.read_csv(RESULTS / "02_monthly_growth.csv", parse_dates=["month_start"])
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(df["month_start"], df["late_pct"], color=RED, linewidth=2, marker="o", markersize=4)
    for _, row in df[df["late_pct"] >= 12].iterrows():
        ax.annotate(f"{row['month_start']:%b %Y}\n{row['late_pct']:.1f}%",
                    (row["month_start"], row["late_pct"]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color=INK)
    ax.set_ylabel("Late deliveries (%)")
    ax.set_ylim(0, 24)
    title(ax, "Late deliveries spike after demand peaks",
          "Share of orders delivered after the promised date, by purchase month")
    fig.tight_layout()
    fig.savefig(IMAGES / "02_late_rate_by_month.png")
    plt.close(fig)


def late_rate_by_state():
    df = pd.read_csv(RESULTS / "03_delivery_by_state.csv").sort_values("late_pct")
    fig, ax = plt.subplots(figsize=(7, 6))
    bars = ax.barh(df["state"], df["late_pct"], color=BLUE, height=0.65)
    ax.bar_label(bars, labels=[f"{v:.1f}%" for v in df["late_pct"]], padding=3, fontsize=8, color=INK)
    ax.set_xlabel("Late deliveries (%)")
    ax.grid(axis="y", visible=False)
    title(ax, "North-east states wait longer and get late orders more often",
          "Late rate by customer state (states with 300+ delivered orders)")
    fig.tight_layout()
    fig.savefig(IMAGES / "03_late_rate_by_state.png")
    plt.close(fig)


def seller_quartiles():
    df = pd.read_csv(RESULTS / "04_seller_scorecard.csv")
    labels = ["Worst 25%", "2nd", "3rd", "Best 25%"]
    colors = [RED, BLUE, BLUE, BLUE]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bars = ax.bar(labels, df["share_of_all_late_orders_pct"], color=colors, width=0.55)
    ax.bar_label(bars, labels=[f"{v:.0f}%" for v in df["share_of_all_late_orders_pct"]], padding=3, color=INK)
    ax.set_ylabel("Share of late orders (%)")
    ax.set_ylim(0, 50)
    ax.grid(axis="x", visible=False)
    title(ax, "A quarter of sellers cause 43% of late orders",
          "Sellers with 50+ delivered orders, grouped into quartiles by late rate")
    fig.tight_layout()
    fig.savefig(IMAGES / "04_seller_quartiles.png")
    plt.close(fig)


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)
    review_by_delivery()
    late_rate_by_month()
    late_rate_by_state()
    seller_quartiles()
    print(f"Charts saved to {IMAGES.name}/")
