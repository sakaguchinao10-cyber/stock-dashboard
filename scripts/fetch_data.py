#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py
tickers.json を読み、yfinance から各銘柄のデータを取得して data.json を出力する。

出力構造:
{
  "updatedAt": "2026-08-15T16:35:00+09:00",
  "indices":  [ {...}, ... ],
  "stocks":   [ {...}, ... ],
  "errors":   [ "7203.T: ..." ]
}
"""

import json
import math
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
TICKERS_FILE = ROOT / "tickers.json"
OUTPUT_FILE = ROOT / "data.json"
JST = timezone(timedelta(hours=9))

# 6ヶ月チャートの間引き後の最大点数（スマホ表示なので粗くて十分）
MAX_CHART_POINTS = 130


# ---------------------------------------------------------------- helpers
def clean(value, digits=2):
    """NaN / inf / None を None に正規化して丸める。"""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, digits)


def sma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def build_links(symbol, exchange=None):
    """
    各サイトの銘柄ページへの閲覧リンク（スクレイピングはせず、リンクのみ）。
    無料・ログイン不要でフル板を表示できるサイトは存在しないため、
    板が必要な場合は証券会社アプリを開くこと。
    """
    if symbol.startswith("^") or "=" in symbol:
        return {}
    if symbol.endswith(".T"):
        code = symbol[:-2]
        return {
            "kabutan": f"https://kabutan.jp/stock/?code={code}",
            "yahoo": f"https://finance.yahoo.co.jp/quote/{symbol}",
            "google": f"https://www.google.com/finance/quote/{code}:{exchange or 'TYO'}?hl=ja",
        }
    return {
        "kabutan": f"https://kabutan.jp/us/stock/?code={symbol}",
        "yahoo": f"https://finance.yahoo.co.jp/quote/{symbol}",
        "google": f"https://www.google.com/finance/quote/{symbol}:{exchange or 'NASDAQ'}?hl=ja",
    }


# ---------------------------------------------------------------- fetchers
def fetch_history(ticker):
    """6ヶ月分の日足を取得し、終値リストと日付リストを返す。"""
    hist = ticker.history(period="6mo", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        return [], []
    hist = hist.dropna(subset=["Close"])
    closes = [float(v) for v in hist["Close"].tolist()]
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]
    return closes, dates


def downsample(closes, dates, limit=MAX_CHART_POINTS):
    n = len(closes)
    if n <= limit:
        return closes, dates
    step = n / limit
    idx = sorted({min(int(i * step), n - 1) for i in range(limit)} | {n - 1})
    return [closes[i] for i in idx], [dates[i] for i in idx]


def fetch_valuation(ticker):
    """PER / PBR / 配当利回り。info は欠損しやすいので個別に握り潰す。"""
    out = {"per": None, "pbr": None, "dividendYield": None}
    try:
        info = ticker.get_info()
    except Exception:
        return out
    if not isinstance(info, dict):
        return out

    out["per"] = clean(info.get("trailingPE"))
    out["pbr"] = clean(info.get("priceToBook"))

    dy = info.get("dividendYield")
    if dy is not None:
        try:
            dy = float(dy)
            # yfinance は 0.032 形式と 3.2 形式が混在するため正規化
            out["dividendYield"] = clean(dy * 100 if dy < 1 else dy)
        except (TypeError, ValueError):
            pass
    return out


def fetch_financials(ticker):
    """
    年次の売上高・純利益を最大4期分取得し、増収・増益の連続期数を判定する。
    yfinance は通期実績のみ提供のため、通期予想に対する進捗率は算出できない。
    """
    result = {"years": [], "revenueUpStreak": None, "incomeUpStreak": None}
    try:
        stmt = ticker.income_stmt
    except Exception:
        return result
    if stmt is None or getattr(stmt, "empty", True):
        return result

    def row(*labels):
        for label in labels:
            if label in stmt.index:
                return stmt.loc[label]
        return None

    revenue = row("Total Revenue", "Operating Revenue")
    income = row("Net Income", "Net Income Common Stockholders")
    if revenue is None:
        return result

    # 列は新しい順に並ぶので古い順へ反転
    cols = list(stmt.columns)[::-1][-5:]
    for col in cols:
        try:
            rev = revenue.get(col)
            inc = income.get(col) if income is not None else None
        except Exception:
            continue
        result["years"].append(
            {
                "fy": col.strftime("%Y") if hasattr(col, "strftime") else str(col),
                "revenue": clean(rev, 0),
                "income": clean(inc, 0),
            }
        )

    def streak(key):
        vals = [y[key] for y in result["years"] if y[key] is not None]
        if len(vals) < 2:
            return None
        count = 0
        # 新しい方から遡って連続増加を数える
        for i in range(len(vals) - 1, 0, -1):
            if vals[i] > vals[i - 1]:
                count += 1
            else:
                break
        return count

    result["revenueUpStreak"] = streak("revenue")
    result["incomeUpStreak"] = streak("income")
    return result


def compute_score(closes, last5, val, fin):
    """
    参考スコア（0〜6）。外部サイトの投資判断は転載できないため、
    公開データから自前で機械的に算出した指標。投資助言ではない。
    """
    reasons = []
    score = 0
    if not closes:
        return {"score": None, "max": 6, "reasons": reasons}

    price = closes[-1]
    ma25 = sma(closes, 25)
    ma75 = sma(closes, 75)

    if ma25 and price > ma25:
        score += 1
        reasons.append("株価>25日線")
    if ma25 and ma75 and ma25 > ma75:
        score += 1
        reasons.append("25日線>75日線")
    if last5 and sum(d["pct"] for d in last5 if d["pct"] is not None) > 0:
        score += 1
        reasons.append("直近5日プラス")
    if val.get("per") is not None and 0 < val["per"] < 15:
        score += 1
        reasons.append("PER<15")
    if val.get("pbr") is not None and 0 < val["pbr"] < 1.0:
        score += 1
        reasons.append("PBR<1.0")
    if (fin.get("revenueUpStreak") or 0) >= 1 and (fin.get("incomeUpStreak") or 0) >= 1:
        score += 1
        reasons.append("増収増益")

    return {"score": score, "max": 6, "reasons": reasons}


def period_change(closes, days):
    """days 営業日前からの騰落率(%)。"""
    if len(closes) <= days:
        return None
    return clean((closes[-1] / closes[-1 - days] - 1) * 100)


def build_entry(symbol, name, group, with_details=True, exchange=None):
    ticker = yf.Ticker(symbol)
    closes, dates = fetch_history(ticker)
    if not closes:
        raise RuntimeError("履歴データが空です")

    price = closes[-1]
    prev = closes[-2] if len(closes) > 1 else price
    change = price - prev

    # ① 直近5営業日の日次騰落率
    last5 = []
    for i in range(max(1, len(closes) - 5), len(closes)):
        pct = (closes[i] / closes[i - 1] - 1) * 100 if i > 0 else None
        last5.append({"date": dates[i][5:], "pct": clean(pct)})

    chart_closes, chart_dates = downsample(closes, dates)

    entry = {
        "symbol": symbol,
        "name": name,
        "group": group,
        "currency": "JPY" if symbol.endswith(".T") or symbol == "^N225" else "USD",
        "price": clean(price, 2),
        "prevClose": clean(prev, 2),
        "change": clean(change, 2),
        "changePct": clean((price / prev - 1) * 100) if prev else None,
        "last5": last5,
        "chart": {"dates": chart_dates, "closes": [clean(c, 2) for c in chart_closes]},
        "periods": {
            "1m": period_change(closes, 21),
            "3m": period_change(closes, 63),
            "6m": period_change(closes, len(closes) - 1),
        },
        "links": build_links(symbol, exchange),
    }

    if with_details:
        val = fetch_valuation(ticker)
        fin = fetch_financials(ticker)
        entry["valuation"] = val
        entry["financials"] = fin
        entry["scoring"] = compute_score(closes, last5, val, fin)

    return entry


# ---------------------------------------------------------------- main
def main():
    config = json.loads(TICKERS_FILE.read_text(encoding="utf-8"))
    errors = []
    stocks = []
    indices = []

    for item in config.get("indices", []):
        try:
            e = build_entry(item["symbol"], item["name"], "INDEX", with_details=False)
            e["pin"] = bool(item.get("pin"))
            indices.append(e)
        except Exception as exc:
            errors.append(f"{item['symbol']}: {exc}")
        time.sleep(0.4)

    for item in config.get("tickers", []):
        try:
            stocks.append(
                build_entry(item["symbol"], item["name"], item.get("group", "JP"),
                            exchange=item.get("exchange"))
            )
            print(f"OK   {item['symbol']}")
        except Exception as exc:
            errors.append(f"{item['symbol']}: {exc}")
            print(f"FAIL {item['symbol']}: {exc}", file=sys.stderr)
        time.sleep(0.8)

    payload = {
        "updatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "source": "Yahoo Finance (yfinance)",
        "indices": indices,
        "stocks": stocks,
        "errors": errors,
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\n書き出し完了: {OUTPUT_FILE}  銘柄 {len(stocks)} 件 / 指数 {len(indices)} 件")
    if errors:
        print(f"取得失敗 {len(errors)} 件: {errors}")
    # 全滅した場合のみ異常終了
    if not stocks and not indices:
        sys.exit(1)


if __name__ == "__main__":
    main()
