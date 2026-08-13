#!/usr/bin/env python3
"""根据最新 sw_snapshot CSV 出图：当日 + 近20日双指标横向条形。"""
from __future__ import annotations
import glob, os, sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

# 中文字体
for fp in ["/System/Library/Fonts/PingFang.ttc",
           "/System/Library/Fonts/STHeiti Medium.ttc",
           "/System/Library/Fonts/Hiragino Sans GB.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "research", "data")


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "sw_l1_*.csv")))
    if not files:
        print("no csv"); sys.exit(1)
    f = files[-1]
    df = pd.read_csv(f)
    snap = df["snapshot_date"].iloc[0]
    print(f"latest: {f}")

    for col, title, fname in [
        ("d1_pct", f"申万一级行业当日涨跌（{snap}）", f"sw_l1_d1_{snap}.png"),
        ("d20_pct", f"申万一级行业近20日涨跌（截至 {snap}）", f"sw_l1_d20_{snap}.png"),
        ("ytd_pct", f"申万一级行业 YTD 涨跌（{snap}）", f"sw_l1_ytd_{snap}.png"),
    ]:
        d = df.dropna(subset=[col]).sort_values(col)
        fig, ax = plt.subplots(figsize=(9, 10))
        colors = ["#d9534f" if v > 0 else "#5cb85c" for v in d[col]]
        ax.barh(d["name"], d[col], color=colors, edgecolor="white")
        ax.axvline(0, color="#333", lw=0.6)
        for i, v in enumerate(d[col]):
            ax.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:+.1f}%",
                    va="center", ha="left" if v >= 0 else "right", fontsize=9)
        ax.set_title(title, fontsize=13, pad=12)
        ax.set_xlabel("%")
        ax.margins(x=0.1)
        ax.grid(axis="x", alpha=0.25)
        plt.tight_layout()
        out = os.path.join(HERE, "research", "data", fname)
        plt.savefig(out, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"chart: {out}")


if __name__ == "__main__":
    main()
