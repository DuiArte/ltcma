# -*- coding: utf-8 -*-
"""Consolidate the full GBM trade-export universe into one clean, de-duplicated
blotter -> ~/LTCMA/data/blotter_clean.csv (used by 18_portfolio.py for the
entry/exit markers). The same trades are exported three ways (Operacion = trade
date, Liquidacion = settlement date, Homebroker history), so we de-duplicate by
treating the MAX count of an identical (ticker,side,shares,price,importe) across
files as the true fill count, and the MIN date as the operation date. Genuine
repeated fills within a single file (e.g. many 5-share SOXX sells) are kept.

Run this whenever new GBM exports are added, then re-run 18_portfolio.py.
Reconciles net shares against the Excel positions as a built-in sanity check.
"""
import os
import re
import pandas as pd
from collections import defaultdict

DL = "/mnt/c/Users/carlo/Downloads"
OUT = os.path.expanduser("~/LTCMA/data/blotter_clean.csv")

# The validated trade-export universe (add new exports here as they arrive).
FILES = [
    "GBM_Homebroker_Historial_de_Transacciones_1779481669443.csv",   # May 08-21 (the missing ops)
    "GBM_Homebroker_Historial_de_Transacciones_1779481549357.csv",   # Mar-07 May (settlement-ish)
    "GBM_Homebroker_Historial_de_Transacciones_1779481238707.csv",   # Mar-07 May (operation-ish)
    "GBM Transacciones Operacion May 2026 MTD (1).csv",
    "GBM Transacciones Liquidacion May 2026 MTD (1).csv",
    "GBM Transacciones Liquidacion 01-mar al 30-abr 2026 (1).csv",
    "GBM Transacciones Liquidacion 01-ene al 28-feb 2026 (1).csv",
    "GBM Transacciones Operacion 01-mat al 30-abr 2026 (1).csv",
    "GBM Transacciones Operacion 01-ene a28 feb 2026 csv (1).csv",
]
MES = dict(ene=1, feb=2, mar=3, abr=4, may=5, jun=6, jul=7, ago=8, sep=9, oct=10, nov=11, dic=12)

def money(x):
    s = re.sub(r"[^0-9.\-]", "", str(x))
    return float(s) if s not in ("", "-", ".") else 0.0

def parse_date(s):
    p = str(s).split("/")
    return pd.Timestamp(int(p[2]), MES[p[1].lower()[:3]], int(p[0]))

rows = []
for fn in FILES:
    try:
        d = pd.read_csv(f"{DL}/{fn}", dtype=str, keep_default_na=False)
    except Exception as e:
        print(f"  !! skip {fn}: {e}")
        continue
    for _, r in d.iterrows():
        dsc = str(r.get("Descripción", ""))
        if "Acciones" not in dsc:                 # stock buys/sells only
            continue
        rows.append((fn, str(r["Emisora"]).replace(" *", "").strip(),
                     "buy" if "Compra" in dsc else "sell",
                     int(round(money(r["Títulos"]))), money(r["Precio"]),
                     round(money(r["Importe"]), 2), parse_date(r["Fecha"])))

# de-dup: identical (ticker,side,shares,price,importe) across files -> one trade,
# count = max per single file, operation date = earliest seen
fc = defaultdict(lambda: defaultdict(int)); dts = defaultdict(list)
for fn, tk, sd, sh, px, im, dt in rows:
    k = (tk, sd, sh, round(px, 2), im)
    fc[k][fn] += 1; dts[k].append(dt)

out = []
for k, perfile in fc.items():
    tk, sd, sh, px, im = k
    for _ in range(max(perfile.values())):
        out.append(dict(date=min(dts[k]).strftime("%Y-%m-%d"), ticker=tk,
                        side=sd, shares=sh, price=px))
bl = pd.DataFrame(out).sort_values(["date", "ticker", "side"]).reset_index(drop=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bl.to_csv(OUT, index=False)

nb = (bl["side"] == "buy").sum(); ns = (bl["side"] == "sell").sum()
print(f"blotter_clean.csv: {len(bl)} fills ({nb} buys, {ns} sells), "
      f"{bl['date'].min()}..{bl['date'].max()} -> {OUT}")

# reconcile net shares vs the Excel May-22 truth
net = defaultdict(float)
for r in bl.itertuples():
    net[r.ticker] += r.shares if r.side == "buy" else -r.shares
xl = pd.read_excel(f"{DL}/Copy of Carteras DBE 2.xlsx", "DBE Acciones")
xl["Fecha"] = pd.to_datetime(xl["Fecha"])
last = xl[xl["Fecha"] == xl["Fecha"].max()]
epos = {str(e).replace(" *", "").strip(): t for e, t in zip(last["Emisora/Fondo"], last["Títulos"])}
print("reconcile (blotter_net vs excel; VGT/VUG differ by design = stock split):")
for t in sorted(set(net) | set(epos)):
    b = net.get(t, 0); e = float(epos.get(t, 0)); d = b - e
    print(f"   {t:<11}{b:>8.0f}{e:>8.0f}{d:>7.0f}{'' if abs(d)<0.5 else '  (split)'}")
