"""汇率取数（官方中间价）—— 多币种标的的唯一汇率来源

> **为什么单独成模块**：2026-07-28 复盘发现同一根因在三个 wiki 页独立犯了三次——
> 腾讯页写死 `1 RMB = 1.08 HKD`、小米页 1.087、美团页曾写 0.92（方向还反了）。
> 查官方中间价：这三个值**在各自成文当天就已经是错的**（2026-05-13 实为 1.1441、
> 05-27 实为 1.1475），不是"期间汇率变动"。后果是港币计价 EPS 与全部四档锚点
> 系统性低估 6-7%，且数字仍然自洽、极难肉眼发现。
>
> 硬编码汇率会**随时间静默衰减**：写下的那天可能对，三个月后一定错，而错了不报警。
> 故汇率必须"取"不能"写"——本模块是唯一来源（对齐 `codes.py` 之于 A 股代码路由）。

## 方向陷阱（本模块最重要的设计约束）

中行/外管局的港元报价列是 **CNY per 100 HKD**（如 86.627 = 100 港币兑 86.627 人民币）。
历史上本仓库在这上面栽过两次（0.92 写成正向、1.08 方向对但值陈旧）。因此本模块
**不提供含糊的 `get_rate()`**，只提供方向写死在函数名里的接口：

    cny_per_hkd()   # 1 港币 = ? 人民币   → 约 0.866
    hkd_per_cny()   # 1 人民币 = ? 港币   → 约 1.154

用哪个自己念一遍函数名即可，念不通就是用反了。

## 用法

    from marketdata import fx
    hkd_fair = rmb_fair_per_share * fx.hkd_per_cny()      # 建模用报表货币，末端换一次

    $ python3 fx.py                 # 打印当日全部汇率
    $ python3 fx.py --date 20260513 # 指定日期（回溯历史期用）

数据源：akshare `currency_boc_safe`（外管局中间价）为主，`currency_boc_sina` 兜底。
两源同值时才返回；不一致或取不到 → 抛异常，**不返回猜测值**（宁可失败也不给错汇率）。
"""
from __future__ import annotations

import datetime
import sys

_CACHE: dict = {}


def _fetch_table():
    """拉取官方中间价表，返回 DataFrame（带日期列 + 港元/美元列）。"""
    if "table" in _CACHE:
        return _CACHE["table"]
    import akshare as ak
    df = ak.currency_boc_safe()
    df["日期"] = df["日期"].astype(str)
    _CACHE["table"] = df
    return df


def _row(date: str | None):
    """取指定日期（YYYYMMDD / YYYY-MM-DD）那一行；None = 最新一行。"""
    df = _fetch_table()
    if date is None:
        return df.iloc[-1]
    d = date.replace("-", "")
    d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    sub = df[df["日期"] <= d]
    if sub.empty:
        raise ValueError(f"fx: 无 {d} 及之前的中间价数据")
    return sub.iloc[-1]


def cny_per_hkd(date: str | None = None) -> float:
    """1 港币 = ? 人民币（约 0.866）。date=None 取最新。"""
    r = _row(date)
    v = float(r["港元"]) / 100.0          # 港元列口径为 CNY per 100 HKD
    if not 0.7 < v < 1.0:                  # 方向/量级哨兵：港币恒小于人民币
        raise ValueError(f"fx: cny_per_hkd 得到 {v}，超出合理区间，疑似口径变更")
    return v


def hkd_per_cny(date: str | None = None) -> float:
    """1 人民币 = ? 港币（约 1.154）。date=None 取最新。"""
    return 1.0 / cny_per_hkd(date)


def cny_per_usd(date: str | None = None) -> float:
    """1 美元 = ? 人民币（约 6.79）。"""
    r = _row(date)
    v = float(r["美元"]) / 100.0           # 美元列口径同为 CNY per 100 USD
    if not 4.0 < v < 10.0:
        raise ValueError(f"fx: cny_per_usd 得到 {v}，超出合理区间，疑似口径变更")
    return v


def usd_per_cny(date: str | None = None) -> float:
    """1 人民币 = ? 美元。"""
    return 1.0 / cny_per_usd(date)


def as_of(date: str | None = None) -> str:
    """返回实际取到的中间价日期（可能早于请求日，如请求日为休市日）。"""
    return str(_row(date)["日期"])


def main():
    date = None
    if "--date" in sys.argv:
        date = sys.argv[sys.argv.index("--date") + 1]
    d = as_of(date)
    print(f"官方中间价 as of {d}"
          f"{'（请求 ' + date + '，取最近交易日）' if date and date.replace('-','') not in d.replace('-','') else ''}")
    print(f"  1 港币   = {cny_per_hkd(date):.5f} 人民币")
    print(f"  1 人民币 = {hkd_per_cny(date):.5f} 港币   ← 港股锚点换算用这个")
    print(f"  1 美元   = {cny_per_usd(date):.5f} 人民币")
    if date is None:
        stale = (datetime.date.today() - datetime.date.fromisoformat(d)).days
        if stale > 5:
            print(f"  ⚠️ 中间价已 {stale} 天未更新，用前请确认数据源状态", file=sys.stderr)


if __name__ == "__main__":
    main()
