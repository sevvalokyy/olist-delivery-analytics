"""
Build an interactive dashboard (docs/index.html) from olist.duckdb.
The page is published with GitHub Pages from the docs/ folder.

Run from the repo root after etl/load.py:
    python make_dashboard.py
"""

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "index.html"

DELIVERED = "f.order_status = 'delivered' AND f.order_delivered_customer_date IS NOT NULL"


def query(con, sql):
    df = con.execute(sql).df()
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build_data(con):
    kpis = query(con, f"""
        SELECT COUNT(*) AS orders,
               ROUND(AVG(delivery_days), 1) AS avg_delivery_days,
               ROUND(AVG(promised_days), 1) AS avg_promised_days,
               ROUND(100 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 1) AS late_pct,
               ROUND(AVG(review_score), 2) AS avg_review
        FROM fact_orders f WHERE {DELIVERED}""")[0]

    reviews = query(con, (ROOT / "sql/analysis/01_late_delivery_vs_review.sql").read_text())
    sellers = query(con, (ROOT / "sql/analysis/04_seller_scorecard.sql").read_text())

    # Monthly late rate per state (plus "All"), so the page can filter by state.
    monthly = query(con, f"""
        SELECT COALESCE(c.state, 'All') AS state,
               STRFTIME(d.month_start, '%Y-%m') AS month,
               COUNT(*) AS orders,
               ROUND(100 * AVG(CASE WHEN f.is_late THEN 1 ELSE 0 END), 1) AS late_pct,
               ROUND(AVG(f.delivery_days), 1) AS avg_delivery_days
        FROM fact_orders f
        JOIN dim_customer c USING (customer_id)
        JOIN dim_date d ON d.date_key = f.purchase_date
        WHERE {DELIVERED}
          AND d.month_start BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
        GROUP BY GROUPING SETS ((c.state, d.month_start), (d.month_start))
        ORDER BY state, month""")

    states = query(con, (ROOT / "sql/analysis/03_delivery_by_state.sql").read_text())
    # Only offer states with enough orders (same 300+ cut as query 03) in the filter.
    keep = {s["state"] for s in states} | {"All"}
    monthly = [r for r in monthly if r["state"] in keep]
    return {"kpis": kpis, "reviews": reviews, "sellers": sellers, "monthly": monthly, "states": states}


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist Delivery Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #f6f5f2; --surface: #fcfcfb; --border: #e4e3df;
    --ink: #0b0b0b; --ink-2: #52514e; --grid: #ecebe7;
    --blue: #2a78d6; --red: #e34948;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #121211; --surface: #1a1a19; --border: #2c2c2a;
      --ink: #f0efec; --ink-2: #c3c2b7; --grid: #2a2a28;
      --blue: #3987e5; --red: #e66767;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 1120px; margin: 0 auto; padding: 32px 16px 48px; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  .sub { color: var(--ink-2); margin: 0 0 24px; }
  .sub a { color: var(--blue); }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .kpi, .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
  .kpi { padding: 14px 16px; }
  .kpi .label { color: var(--ink-2); font-size: 13px; }
  .kpi .value { font-size: 26px; font-weight: 650; margin-top: 2px; }
  .kpi .note { color: var(--ink-2); font-size: 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr)); gap: 16px; }
  .card { padding: 18px 18px 12px; min-width: 0; }
  .card h2 { font-size: 16px; margin: 0; }
  .card p { color: var(--ink-2); font-size: 13px; margin: 2px 0 12px; }
  .wide { grid-column: 1 / -1; }
  .chart { position: relative; height: 280px; }
  .tall { height: 520px; }
  .row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
  select { font: inherit; color: var(--ink); background: var(--surface); border: 1px solid var(--border);
           border-radius: 8px; padding: 6px 10px; }
  footer { color: var(--ink-2); font-size: 12px; margin-top: 24px; }
</style>
</head>
<body>
<main>
  <h1>Olist delivery &amp; seller performance</h1>
  <p class="sub">~96k delivered orders from a Brazilian e-commerce marketplace, Jan 2017 – Aug 2018.
    Source code and SQL: <a href="https://github.com/sevvalokyy/olist-delivery-analytics">GitHub</a></p>

  <section class="kpis" id="kpis"></section>

  <section class="grid">
    <div class="card wide">
      <div class="row">
        <div>
          <h2>Late delivery rate by month</h2>
          <p>Share of orders delivered after the promised date, by purchase month</p>
        </div>
        <label>State <select id="state"></select></label>
      </div>
      <div class="chart"><canvas id="monthly"></canvas></div>
    </div>

    <div class="card">
      <h2>Review score vs. delivery time</h2>
      <p>Average review by how early or late the order arrived</p>
      <div class="chart"><canvas id="reviews"></canvas></div>
    </div>

    <div class="card">
      <h2>Late orders by seller quartile</h2>
      <p>Sellers with 50+ delivered orders, grouped by their late rate</p>
      <div class="chart"><canvas id="sellers"></canvas></div>
    </div>

    <div class="card wide">
      <h2>Late rate by customer state</h2>
      <p>States with 300+ delivered orders. Hover for delivery time and review score.</p>
      <div class="chart tall"><canvas id="states"></canvas></div>
    </div>
  </section>

  <footer>Built with Python, DuckDB and Chart.js. Data: Olist public dataset (Kaggle).</footer>
</main>

<script>
const DATA = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = { ink: css('--ink'), ink2: css('--ink-2'), grid: css('--grid'), blue: css('--blue'), red: css('--red'), surface: css('--surface') };

Chart.defaults.color = C.ink2;
Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
Chart.defaults.plugins.legend.display = false;
Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
Chart.defaults.plugins.tooltip.titleColor = C.surface;
Chart.defaults.plugins.tooltip.bodyColor = C.surface;
Chart.defaults.maintainAspectRatio = false;
const axis = (title, extra = {}) => ({ grid: { color: C.grid }, border: { display: false },
  title: { display: !!title, text: title }, ...extra });
const noGrid = { grid: { display: false }, border: { color: C.grid } };
const fmt = n => n.toLocaleString('en-US');

// KPI tiles
const k = DATA.kpis;
const tiles = [
  ['Delivered orders', fmt(k.orders), ''],
  ['Avg. delivery time', k.avg_delivery_days + ' days', 'promised: ' + k.avg_promised_days + ' days'],
  ['Late deliveries', k.late_pct + '%', 'after the promised date'],
  ['Avg. review score', k.avg_review + ' / 5', ''],
];
document.getElementById('kpis').innerHTML = tiles.map(([l, v, n]) =>
  `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="note">${n || '&nbsp;'}</div></div>`).join('');

// Monthly late rate with state filter
const sel = document.getElementById('state');
const stateList = ['All', ...[...new Set(DATA.monthly.map(r => r.state).filter(s => s !== 'All'))].sort()];
sel.innerHTML = stateList.map(s => `<option>${s}</option>`).join('');
const monthlyFor = s => DATA.monthly.filter(r => r.state === s);
const monthly = new Chart(document.getElementById('monthly'), {
  type: 'line',
  data: { labels: monthlyFor('All').map(r => r.month),
          datasets: [{ data: monthlyFor('All').map(r => r.late_pct), borderColor: C.red, backgroundColor: C.red,
                       borderWidth: 2, pointRadius: 3, pointHoverRadius: 6, tension: 0.25 }] },
  options: {
    interaction: { mode: 'index', intersect: false },
    scales: { y: axis('Late deliveries (%)', { beginAtZero: true }), x: noGrid },
    plugins: { tooltip: { callbacks: {
      label: ctx => {
        const r = monthlyFor(sel.value)[ctx.dataIndex];
        return [`Late: ${r.late_pct}%`, `Orders: ${fmt(r.orders)}`, `Avg. delivery: ${r.avg_delivery_days} days`];
      } } } }
  }
});
sel.addEventListener('change', () => {
  const rows = monthlyFor(sel.value);
  monthly.data.labels = rows.map(r => r.month);
  monthly.data.datasets[0].data = rows.map(r => r.late_pct);
  monthly.update();
});

// Review score by delivery bucket
new Chart(document.getElementById('reviews'), {
  type: 'bar',
  data: { labels: DATA.reviews.map(r => r.delivery_bucket.slice(3)),
          datasets: [{ data: DATA.reviews.map(r => r.avg_review),
                       backgroundColor: DATA.reviews.map(r => r.delivery_bucket.includes('late') ? C.red : C.blue),
                       borderRadius: 4, maxBarThickness: 48 }] },
  options: {
    scales: { y: axis('Avg. review (1-5)', { min: 0, max: 5 }), x: noGrid },
    plugins: { tooltip: { callbacks: { label: ctx => {
      const r = DATA.reviews[ctx.dataIndex];
      return [`Avg. review: ${r.avg_review}`, `1-2 star reviews: ${r.pct_1_2_star}%`, `Orders: ${fmt(r.orders)}`];
    } } } }
  }
});

// Seller quartiles
const qLabels = ['Worst 25%', '2nd', '3rd', 'Best 25%'];
new Chart(document.getElementById('sellers'), {
  type: 'bar',
  data: { labels: qLabels,
          datasets: [{ data: DATA.sellers.map(r => r.share_of_all_late_orders_pct),
                       backgroundColor: DATA.sellers.map((r, i) => i === 0 ? C.red : C.blue),
                       borderRadius: 4, maxBarThickness: 56 }] },
  options: {
    scales: { y: axis('Share of late orders (%)', { beginAtZero: true }), x: noGrid },
    plugins: { tooltip: { callbacks: { label: ctx => {
      const r = DATA.sellers[ctx.dataIndex];
      return [`Share of late orders: ${r.share_of_all_late_orders_pct}%`, `Sellers: ${r.sellers}`,
              `Late rate: ${r.late_pct}%`, `Avg. review: ${r.avg_review}`];
    } } } }
  }
});

// States
new Chart(document.getElementById('states'), {
  type: 'bar',
  data: { labels: DATA.states.map(r => r.state),
          datasets: [{ data: DATA.states.map(r => r.late_pct), backgroundColor: C.blue, borderRadius: 4, barPercentage: 0.75 }] },
  options: {
    indexAxis: 'y',
    scales: { x: axis('Late deliveries (%)', { beginAtZero: true }), y: { grid: { display: false }, border: { display: false } } },
    plugins: { tooltip: { callbacks: { label: ctx => {
      const r = DATA.states[ctx.dataIndex];
      return [`Late: ${r.late_pct}%`, `Orders: ${fmt(r.orders)}`, `Avg. delivery: ${r.avg_delivery_days} days`,
              `Promised: ${r.avg_promised_days} days`, `Avg. review: ${r.avg_review}`];
    } } } }
  }
});
</script>
</body>
</html>
"""


def main():
    con = duckdb.connect(str(ROOT / "olist.duckdb"), read_only=True)
    data = build_data(con)
    con.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(PAGE.replace("__DATA__", json.dumps(data)), encoding="utf-8")
    print(f"Dashboard written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
