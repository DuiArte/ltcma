"""Visualization suite for the LTCMA report.
Saves PNG figures to report/figures/.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from paths import DATA_S as D  # repo-anchored (2026-06-10)
import paths as _paths
FIG = str(_paths.REPORT / "figures")
os.makedirs(FIG, exist_ok=True)
NAVY, GOLD, RED, GREY = "#1a3a5c", "#c8961e", "#a23b3b", "#8a9099"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.edgecolor": "#888", "axes.titleweight": "bold",
                     "axes.titlecolor": NAVY, "figure.dpi": 130})

ret = pd.read_csv(f"{D}/ltcma_returns.csv", index_col=0)
summ = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
vol = pd.read_csv(f"{D}/ltcma_vol_v2.csv", index_col=0)["vol_blended"]
cov = pd.read_csv(f"{D}/ltcma_cov_v2.csv", index_col=0)

# ---------- 1. valuation dispersion ----------
eq = ret[ret["class"] == "Equity"].copy()
eq = eq.sort_values("val_now")
fig, ax = plt.subplots(figsize=(7.2, 3.6))
colors = [RED if v > 25 else (GOLD if v > 18 else NAVY) for v in eq["val_now"]]
ax.bar(range(len(eq)), eq["val_now"], color=colors)
ax.set_xticks(range(len(eq)))
ax.set_xticklabels([i.replace("_", " ") for i in eq.index], rotation=40, ha="right")
ax.set_ylabel("CAPE / trailing P/E")
ax.set_title("Valuation dispersion — equity markets (cheap to rich)")
ax.legend(handles=[Patch(color=NAVY, label="cheap"), Patch(color=GOLD, label="fair"),
                   Patch(color=RED, label="rich")], frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_valuation.png"); plt.close(fig)

# ---------- 2. return vs risk map ----------
cmap = {"Equity": NAVY, "Fixed Income": GOLD, "Real Asset": RED}
fig, ax = plt.subplots(figsize=(7.2, 4.6))
for _, r in summ.iterrows():
    ax.scatter(r["vol"] * 100, r["ER_lambda0.5"] * 100, s=46,
               color=cmap.get(r["class"], GREY), zorder=3, edgecolor="white")
for a in summ.index:
    ax.annotate(a.replace("_", " "), (summ.loc[a, "vol"] * 100,
                summ.loc[a, "ER_lambda0.5"] * 100), fontsize=6.4,
                xytext=(4, 3), textcoords="offset points")
ax.set_xlabel("Volatility (%)"); ax.set_ylabel("Expected return, base case (%)")
ax.set_title("Risk / return map — 12-year LTCMA")
ax.grid(alpha=.25)
ax.legend(handles=[Patch(color=c, label=k) for k, c in cmap.items()],
          frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_return_risk.png"); plt.close(fig)

# ---------- 3. equity building-block decomposition ----------
eqd = ret[ret["class"] == "Equity"].copy().sort_values("ER_lambda0.5")
comp = ["DY", "BB", "g_real", "infl"]
labels = {"DY": "dividend", "BB": "buyback", "g_real": "real EPS growth",
          "infl": "US inflation"}
ccol = {"DY": NAVY, "BB": "#3d6a96", "g_real": GOLD, "infl": GREY}
fig, ax = plt.subplots(figsize=(7.2, 3.8))
bottom = np.zeros(len(eqd))
for c in comp:
    ax.barh(range(len(eqd)), eqd[c] * 100, left=bottom, color=ccol[c],
            label=labels[c])
    bottom += eqd[c].values * 100
ax.scatter(eqd["ER_lambda0.5"] * 100, range(len(eqd)), color=RED, zorder=5,
           label="= expected return", s=34)
ax.set_yticks(range(len(eqd)))
ax.set_yticklabels([i.replace("_", " ") for i in eqd.index])
ax.set_xlabel("%"); ax.set_title("Equity expected-return building blocks "
              "(red dot = ER after valuation reversion)")
ax.legend(frameon=False, fontsize=7.5, ncol=5, loc="lower right")
fig.tight_layout(); fig.savefig(f"{FIG}/fig_building_blocks.png"); plt.close(fig)

# ---------- 4. correlation heatmap ----------
corr = pd.read_csv(f"{D}/ltcma_corr_v2.csv", index_col=0)
fig, ax = plt.subplots(figsize=(8.4, 7.2))
im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr))); ax.set_yticks(range(len(corr)))
ax.set_xticklabels([c.replace("_", " ") for c in corr.columns], rotation=90, fontsize=6.5)
ax.set_yticklabels([c.replace("_", " ") for c in corr.index], fontsize=6.5)
ax.set_title("Asset correlation matrix (Ledoit-Wolf shrunk)")
fig.colorbar(im, fraction=0.046, pad=0.04)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_correlation.png"); plt.close(fig)

# ---------- 5. Monte Carlo fan chart (per portfolio) ----------
PORT = {
    "Conservative 30/70": {"US_LargeCap": .14, "DM_exUS_Eq": .08, "EM_Eq": .08,
        "US_Treas_Interm": .25, "US_IG_Corp": .15, "Global_Agg_exUS": .10,
        "US_Cash_TBill": .12, "US_HighYield": .04, "EM_USD_Sov": .04},
    "Moderate 60/40": {"US_LargeCap": .30, "DM_exUS_Eq": .16, "EM_Eq": .14,
        "US_Treas_Interm": .18, "US_IG_Corp": .10, "Global_Agg_exUS": .06,
        "US_HighYield": .03, "EM_USD_Sov": .03},
    "Growth 90/10": {"US_LargeCap": .42, "DM_exUS_Eq": .26, "EM_Eq": .22,
        "US_Treas_Interm": .05, "US_IG_Corp": .03, "EM_USD_Sov": .02},
    "Edge-Tilted": {"US_LargeCap": .16, "DM_exUS_Eq": .14, "EM_Eq": .16,
        "Mexico_Eq": .07, "Japan_Eq": .07, "EM_USD_Sov": .08,
        "Mexico_Govt_Local": .09, "US_TIPS": .08, "US_Treas_Interm": .07,
        "Gold": .05, "US_Cash_TBill": .03}}
assets = list(cov.index)
er = summ.loc[assets, "ER_lambda0.5"]
rng = np.random.default_rng(20260518)
fig, axes = plt.subplots(2, 2, figsize=(8.6, 6.0), sharex=True)
for ax, (name, w) in zip(axes.ravel(), PORT.items()):
    wv = np.array([w.get(a, 0) for a in assets])
    mp = float(wv @ er.values)
    sp = float(np.sqrt(wv @ cov.values @ wv))
    ml = np.log(1 + mp) - 0.5 * np.log(1 + sp**2 / (1 + mp)**2)
    sl = np.sqrt(np.log(1 + sp**2 / (1 + mp)**2))
    paths = np.cumprod(np.exp(rng.normal(ml, sl, (20000, 12))), axis=1)
    paths = np.column_stack([np.ones(20000), paths])
    yr = np.arange(13)
    for lo, hi, a in [(5, 95, .18), (25, 75, .30)]:
        ax.fill_between(yr, np.percentile(paths, lo, 0), np.percentile(paths, hi, 0),
                        color=NAVY, alpha=a)
    ax.plot(yr, np.percentile(paths, 50, 0), color=NAVY, lw=1.8)
    ax.axhline(1, color=GREY, lw=.8, ls="--")
    ax.set_title(name, fontsize=9)
    ax.set_xlim(0, 12); ax.grid(alpha=.2)
for ax in axes[:, 0]:
    ax.set_ylabel("growth of $1")
for ax in axes[1, :]:
    ax.set_xlabel("year")
fig.suptitle("Monte Carlo outcome fans — 5/25/50/75/95 percentiles",
             fontweight="bold", color=NAVY)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_mc_fan.png"); plt.close(fig)

# ---------- 6. regime timeline ----------
gpr = pd.read_excel(f"{D}/signals_gpr_raw.xls")[["month", "GPR"]].set_index("month")["GPR"]
gpr.index = gpr.index + pd.offsets.MonthEnd(0)
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
epu = sig["EPU_US"].dropna(); epu.index = epu.index + pd.offsets.MonthEnd(0)
epu = epu.groupby(epu.index).last()
idx = gpr.index.intersection(epu.index)
idx = idx[idx >= "2000-01-01"]
z = lambda s: (s - s.loc[idx].mean()) / s.loc[idx].std()
score = (z(gpr).loc[idx] + z(epu).loc[idx]) / 2
thr = score.quantile(2 / 3)
fig, ax = plt.subplots(figsize=(8.6, 3.2))
ax.plot(idx, gpr.loc[idx], color=RED, lw=.9, label="GPR (geopolitical risk)")
ax.plot(idx, epu.loc[idx], color=NAVY, lw=.9, label="EPU (policy uncertainty)")
for d in idx[score >= thr]:
    ax.axvspan(d - pd.offsets.MonthBegin(1), d, color=GOLD, alpha=.18, lw=0)
ax.set_title("News-uncertainty regimes — shaded = stress months")
ax.set_ylabel("index level"); ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.margins(x=0.01)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_regime_timeline.png"); plt.close(fig)

# ---------- 7. priced-in forward curve ----------
last = sig.ffill().iloc[-1]
TEN = {"UST_3M": .25, "UST_6M": .5, "UST_1Y": 1, "UST_2Y": 2, "UST_3Y": 3,
       "UST_5Y": 5, "UST_7Y": 7, "UST_10Y": 10}
y = {t: last[k] / 100 for k, t in TEN.items()}
ts = sorted(y)
fwd_x, fwd_y = [], []
for t1, t2 in zip(ts[:-1], ts[1:]):
    f = ((1 + y[t2]) ** t2 / (1 + y[t1]) ** t1) ** (1 / (t2 - t1)) - 1
    fwd_x.append((t1 + t2) / 2); fwd_y.append(f * 100)
fig, ax = plt.subplots(figsize=(7.2, 3.6))
ax.plot(ts, [y[t] * 100 for t in ts], "o-", color=NAVY, label="spot Treasury curve")
ax.plot(fwd_x, fwd_y, "s--", color=GOLD, label="implied forward short rate")
ax.axhline(last["FedFunds"], color=RED, ls=":", label=f"current fed funds {last['FedFunds']:.2f}%")
ax.set_xlabel("maturity (years)"); ax.set_ylabel("rate (%)")
ax.set_title("Priced-in rate path — market expects NO cuts")
ax.legend(frameon=False, fontsize=8); ax.grid(alpha=.25)
fig.tight_layout(); fig.savefig(f"{FIG}/fig_priced_in.png"); plt.close(fig)

# ---------- 8. regime vol amplification ----------
lh = pd.read_csv(f"{D}/regime_longhistory.csv", index_col=0)
lh = lh.sort_values("vol_multiple")
fig, ax = plt.subplots(figsize=(7.2, 3.2))
bars = ax.barh([s.replace("_", " ") for s in lh.index],
               lh["vol_multiple"], color=NAVY)
bars[list(lh.index).index("USDMXN")].set_color(RED)
ax.axvline(1, color=GREY, lw=.8)
for i, v in enumerate(lh["vol_multiple"]):
    ax.text(v + .02, i, f"{v:.2f}x", va="center", fontsize=8)
ax.set_xlabel("stress-regime volatility / calm-regime volatility")
ax.set_title("Regime volatility amplification (2000-2026) — peso most sensitive")
fig.tight_layout(); fig.savefig(f"{FIG}/fig_regime_amp.png"); plt.close(fig)

print("Saved 8 figures to", FIG)
for f in sorted(os.listdir(FIG)):
    print("  ", f)
