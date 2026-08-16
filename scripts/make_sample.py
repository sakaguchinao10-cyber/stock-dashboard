#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネットワークなしで index.html の表示を確認するためのサンプル data.json を生成する。"""
import json, math, random
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
random.seed(20260815)

cfg = json.loads((ROOT / "tickers.json").read_text(encoding="utf-8"))


def series(base, n=125, drift=0.0006, vol=0.014):
    """OHLC込みの日足を生成。(opens, highs, lows, closes) を返す。"""
    opens, highs, lows, closes = [], [], [], []
    p = base
    for _ in range(n):
        o = p
        c = o * (1 + random.gauss(drift, vol))
        hi = max(o, c) * (1 + abs(random.gauss(0, 0.006)))
        lo = min(o, c) * (1 - abs(random.gauss(0, 0.006)))
        opens.append(round(o, 2)); highs.append(round(hi, 2))
        lows.append(round(lo, 2)); closes.append(round(c, 2))
        p = c
    return opens, highs, lows, closes


def bars(o, h, l, c, dates, days):
    n = len(c); k = min(days, n)
    return [{"d": dates[i][5:], "o": o[i], "h": h[i], "l": l[i], "c": c[i]}
            for i in range(n - k, n)]


EXCH = {}  # sym -> exchange（cfgから後で埋める）
def entry(sym, name, group, base, details=True):
    opens, highs, lows, closes = series(base)
    d0 = datetime(2026, 2, 16)
    dates = [(d0 + timedelta(days=int(i * 1.72))).strftime("%Y-%m-%d") for i in range(len(closes))]
    price, prev = closes[-1], closes[-2]
    last5 = [{"date": dates[i][5:], "pct": round((closes[i] / closes[i - 1] - 1) * 100, 2)}
             for i in range(len(closes) - 5, len(closes))]
    # 3M折れ線は63点を間引き
    l3 = closes[-63:]; d3 = dates[-63:]
    step = max(1, len(l3) // 60)
    line_c = l3[::step]; line_d = d3[::step]
    if line_d[-1] != d3[-1]:
        line_c.append(l3[-1]); line_d.append(d3[-1])
    e = {
        "symbol": sym, "name": name, "group": group,
        "currency": "JPY" if sym.endswith(".T") or sym == "^N225" else "USD",
        "price": price, "prevClose": prev,
        "change": round(price - prev, 2),
        "changePct": round((price / prev - 1) * 100, 2),
        "last5": last5,
        "chart": {
            "line3m": {"dates": line_d, "closes": line_c},
            "ohlc1m": bars(opens, highs, lows, closes, dates, 21),
            "ohlc2w": bars(opens, highs, lows, closes, dates, 10),
        },
        "periods": {
            "1m": round((closes[-1] / closes[-22] - 1) * 100, 2),
            "3m": round((closes[-1] / closes[-64] - 1) * 100, 2),
            "6m": round((closes[-1] / closes[0] - 1) * 100, 2),
        },
        "links": ({} if sym.startswith("^") or "=" in sym else
                  ({"kabutan": f"https://kabutan.jp/stock/?code={sym[:-2]}",
                    "yahoo": f"https://finance.yahoo.co.jp/quote/{sym}",
                    "google": f"https://www.google.com/finance/quote/{sym[:-2]}:TYO?hl=ja"}
                   if sym.endswith(".T") else
                   {"kabutan": f"https://kabutan.jp/us/stock/?code={sym}",
                    "yahoo": f"https://finance.yahoo.co.jp/quote/{sym}",
                    "google": f"https://www.google.com/finance/quote/{sym}:{EXCH.get(sym,'NASDAQ')}?hl=ja"})),
    }
    if details:
        rev = 1.0e12 * random.uniform(0.4, 3.0)
        years = []
        for k, fy in enumerate(["2023", "2024", "2025", "2026"]):
            rev *= random.uniform(0.96, 1.14)
            years.append({"fy": fy, "revenue": round(rev), "income": round(rev * random.uniform(0.03, 0.14))})
        per = round(random.uniform(7, 34), 2)
        pbr = round(random.uniform(0.6, 5.5), 2)
        e["valuation"] = {"per": per, "pbr": pbr, "dividendYield": round(random.uniform(0, 4.5), 2)}

        def streak(key):
            v = [y[key] for y in years]
            c = 0
            for i in range(len(v) - 1, 0, -1):
                if v[i] > v[i - 1]:
                    c += 1
                else:
                    break
            return c
        e["financials"] = {"years": years, "revenueUpStreak": streak("revenue"), "incomeUpStreak": streak("income")}
        sc, why = 0, []
        ma25 = sum(closes[-25:]) / 25
        ma75 = sum(closes[-75:]) / 75
        if price > ma25: sc += 1; why.append("株価>25日線")
        if ma25 > ma75: sc += 1; why.append("25日線>75日線")
        if sum(x["pct"] for x in last5) > 0: sc += 1; why.append("直近5日プラス")
        if 0 < per < 15: sc += 1; why.append("PER<15")
        if 0 < pbr < 1.0: sc += 1; why.append("PBR<1.0")
        if e["financials"]["revenueUpStreak"] >= 1 and e["financials"]["incomeUpStreak"] >= 1:
            sc += 1; why.append("増収増益")
        e["scoring"] = {"score": sc, "max": 6, "reasons": why}
    return e


bases = {
  # 日本株
  "7011.T": 3400, "7012.T": 8200, "4661.T": 3600, "9432.T": 158, "6432.T": 4700,
  "2432.T": 2100, "8058.T": 3600, "7203.T": 3180, "7201.T": 480, "7267.T": 1650,
  "6976.T": 4900, "6702.T": 3410, "5965.T": 1120,
  # 米国株
  "AAPL": 232, "MSFT": 470, "GOOG": 205, "AMZN": 231, "TSLA": 340, "NVDA": 178,
  "PLTR": 158, "SOFI": 22, "RBLX": 128, "IONQ": 44,
  # ETF
  "SPCX": 32, "SPHY": 23, "SPYD": 43, "SPYM": 78,
  # 指数
  "^N225": 42800, "^TPX": 3050, "^GSPC": 6420, "^IXIC": 21500,
  "USDJPY=X": 148.6, "EURJPY=X": 172.4,
}


def base_of(sym):
    return bases.get(sym, 1000)


EXCH.update({t["symbol"]: t.get("exchange","NASDAQ") for t in cfg["tickers"]})
payload = {
    "updatedAt": datetime.now(JST).isoformat(timespec="seconds"),
    "source": "サンプルデータ（表示確認用・実データではありません）",
    "indices": [dict(entry(i["symbol"], i["name"], "INDEX", base_of(i["symbol"]), False), pin=bool(i.get("pin"))) for i in cfg["indices"]],
    # ETF は決算・PER/PBR・スコアを持たない（details=False）
    "stocks": [entry(t["symbol"], t["name"], t["group"], base_of(t["symbol"]),
                     details=(t["group"] != "ETF")) for t in cfg["tickers"]],
    "errors": [],
}
(ROOT / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("サンプル data.json を生成しました")
