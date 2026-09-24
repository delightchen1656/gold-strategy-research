"""Plot the return-priority strategy against London and CNY gold proxy."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from research_execution_v2 import Spec, evaluate, load_inputs, START, END

OUT = ROOT / "research" / "return-improvement-2026-09-08"
selected = json.loads((OUT / "result.json").read_text(encoding="utf-8"))["selected"]["spec"]
spec = Spec(**selected)
gold, frame = load_inputs()
_, detail = evaluate(spec, gold, frame, details=True)

# All series are rebased to 100 at the first common strategy date.  Shanghai gold
# is the project’s existing RMB/g proxy: London AM fixing × USD/CNY ÷ 31.1034768.
idx = frame.loc[START:END].index
series = pd.DataFrame(index=idx)
series["London gold (USD/oz)"] = gold.reindex(idx).ffill()
series["Shanghai gold proxy (CNY/g)"] = frame.loc[idx, "cmb_mid"]
for path, label in [("cmb", "Strategy A — CMB gold proxy"),
                    ("fund", "Strategy A — CCB Shanghai Gold ETF A")]:
    s = pd.DataFrame(detail[path]["daily"])
    s["date"] = pd.to_datetime(s["date"])
    series[label] = s.set_index("date")["equity"].reindex(idx).ffill()
series = series.dropna()
rebased = series.div(series.iloc[0]).mul(100)
monthly = rebased.resample("ME").last()
monthly.to_csv(OUT / "strategy_and_gold_index_2021_present.csv", index_label="date", encoding="utf-8-sig")

plt.style.use("seaborn-v0_8-whitegrid")
fig, ax = plt.subplots(figsize=(15, 8), dpi=180)
colors = ["#6b7280", "#d97706", "#0f766e", "#2563eb"]
for (name, values), color in zip(monthly.items(), colors):
    lw = 2.8 if name.startswith("Strategy") else 1.8
    ax.plot(monthly.index, values, label=name, color=color, linewidth=lw)
ax.axhline(100, color="#9ca3af", linewidth=0.8)
ax.set_title("Gold trends and return-priority Strategy A (2021-01-04 to 2026-09-04)", loc="left", weight="bold", fontsize=16, pad=28)
ax.text(0, 1.01, "All series rebased to 100. Strategy curves include trading fees, confirmation and redemption settlement rules.",
        transform=ax.transAxes, fontsize=10, color="#4b5563")
ax.set_ylabel("Indexed value (start = 100)")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.legend(loc="upper left", frameon=True, framealpha=.94)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(rect=(0, 0, 1, .93))
fig.savefig(OUT / "策略A与伦敦金上海金走势_2021至今.png", bbox_inches="tight")
print((OUT / "策略A与伦敦金上海金走势_2021至今.png").resolve())
print(monthly.iloc[[0, -1]].round(2).to_string())

