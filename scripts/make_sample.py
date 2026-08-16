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
    out, p = [], base
    for _ in range(n):
        p *= 1 + random.gauss(drift, vol)
        out.append(round(p, 2))
    return out


def entry(sym, name, group, base, details=True):
    closes = series(base)
    d0 = datetime(2026, 2, 16)
    dates = [(d0 + timedelta(days=int(i * 1.72))).strftime("%Y-%m-%d") for i in range(len(closes))]
    price, prev = closes[-1], closes[-2]
    last5 = [{"date": dates[i][5:], "pct": round((closes[i] / closes[i - 1] - 1) * 100, 2)}
             for i in range(len(closes) - 5, len(closes))]
    e = {
        "symbol": sym, "name": name, "group": group,
        "currency": "JPY" if sym.endswith(".T") or sym == "^N225" else "USD",
        "price": price, "prevClose": prev,
        "change": round(price - prev, 2),
        "changePct": round((price / prev - 1) * 100, 2),
        "last5": last5,
        "chart": {"dates": dates, "closes": closes},
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
                    "google": f"https://www.google.com/finance/quote/{sym}:NASDAQ?hl=ja"})),
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


bases = {"7203.T": 3180, "8306.T": 2240, "6501.T": 4820, "6702.T": 3410, "6861.T": 61200,
         "1605.T": 2190, "9501.T": 685, "AAPL": 232, "MSFT": 470, "NVDA": 178,
         "GOOGL": 205, "AMZN": 231, "^N225": 42800, "^TPX": 3050, "^GSPC": 6420,
         "^IXIC": 21500, "USDJPY=X": 148.6, "EURJPY=X": 172.4}

payload = {
    "updatedAt": datetime.now(JST).isoformat(timespec="seconds"),
    "source": "サンプルデータ（表示確認用・実データではありません）",
    "indices": [dict(entry(i["symbol"], i["name"], "INDEX", bases[i["symbol"]], False), pin=bool(i.get("pin"))) for i in cfg["indices"]],
    "stocks": [entry(t["symbol"], t["name"], t["group"], bases[t["symbol"]]) for t in cfg["tickers"]],
    "errors": [],
}
(ROOT / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("サンプル data.json を生成しました")
