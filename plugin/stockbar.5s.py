#!/usr/bin/env python3
# <xbar.title>Stockbar</xbar.title>
# <xbar.desc>Live stock prices and P&L in the macOS menu bar, with profit alerts.</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

CONFIG = os.path.expanduser(os.environ.get("STOCKBAR_CONFIG", "~/.config/stockbar/holdings.json"))
STATE_DIR = os.environ.get("SWIFTBAR_PLUGIN_DATA_PATH") or os.path.expanduser("~/.cache/stockbar")
SELF = os.path.abspath(__file__)
ALERTS = 5
GREEN, RED = "#2ecc71", "#e74c3c"
CURRENCY = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def load():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"pinned": None, "holdings": []}


def save(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def quote(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
        return get_json(url)["chart"]["result"][0]["meta"]
    except Exception:
        return None


def search(text):
    url = "https://query1.finance.yahoo.com/v1/finance/search?quotesCount=10&newsCount=0&q=" + urllib.parse.quote(text)
    return [q for q in get_json(url).get("quotes", []) if q.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND", "INDEX")]


def osa(lines, *args):
    script = ["-e", "on run argv", *sum([["-e", line] for line in lines], []), "-e", "end run"]
    return subprocess.run(["osascript", *script, *args], capture_output=True, text=True)


def notify(title, message):
    osa(['display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"'], title, message)


def ask(prompt, default=""):
    r = osa(['text returned of (display dialog (item 1 of argv) default answer (item 2 of argv) with title "Stockbar")'], prompt, str(default))
    if r.returncode:
        sys.exit(0)
    return r.stdout.strip()


def ask_number(prompt, default="", optional=False):
    while True:
        text = ask(prompt, default).replace(",", "")
        if optional and not text:
            return None
        try:
            return float(text)
        except ValueError:
            prompt = "Please enter a number.\n\n" + prompt


def choose(prompt, items):
    r = osa(['set r to choose from list (rest of argv) with prompt (item 1 of argv) with title "Stockbar"',
             'if r is false then return ""', 'return item 1 of r'], prompt, *items)
    return r.stdout.strip() or sys.exit(0)


def short(symbol):
    return symbol.split(".")[0]


def money(x, cur, sign=False, decimals=2):
    s = "-" if x < 0 else ("+" if sign else "")
    return f"{s}{CURRENCY.get(cur, cur + ' ')}{abs(x):,.{decimals}f}"


def ask_position(h):
    h["shares"] = ask_number(f"How many shares of {h['symbol']} do you own?", h.get("shares", ""))
    h["buy_price"] = ask_number("Average buy price per share:", h.get("buy_price", ""))
    alert = h.get("alert_below")
    h["alert_below"] = ask_number("Alert me when total profit drops below (leave blank for no alert):",
                                  "" if alert is None else alert, optional=True)


def action(cmd, symbol=None):
    cfg = load()
    holdings = cfg.setdefault("holdings", [])
    match = next((h for h in holdings if h["symbol"] == symbol), None)
    if cmd == "add":
        results = search(ask("Search for a stock by name or symbol:"))
        if not results:
            osa(['display alert "No stocks found" message (item 1 of argv)'], "Try a different name or the exact symbol, e.g. RELIANCE.NS or AAPL.")
            return
        labels = [f"{q['symbol']} | {q.get('longname') or q.get('shortname', '')} ({q.get('exchDisp', '')})" for q in results]
        picked = results[labels.index(choose("Pick the stock:", labels))]
        h = next((x for x in holdings if x["symbol"] == picked["symbol"]), None)
        if not h:
            h = {"symbol": picked["symbol"], "name": picked.get("longname") or picked.get("shortname")}
            holdings.append(h)
        ask_position(h)
        cfg["pinned"] = cfg.get("pinned") or h["symbol"]
    elif cmd == "edit" and match:
        ask_position(match)
    elif cmd == "remove" and match:
        holdings.remove(match)
        if cfg.get("pinned") == symbol:
            cfg["pinned"] = holdings[0]["symbol"] if holdings else None
    elif cmd == "pin":
        cfg["pinned"] = symbol
    save(cfg)


def check_alert(h, profit, price, cur):
    path = os.path.join(STATE_DIR, f"alerts_{h['symbol']}")
    try:
        with open(path) as f:
            sent = int(f.read())
    except (OSError, ValueError):
        sent = 0
    floor = h.get("alert_below")
    low = floor is not None and profit < floor
    if low and sent < ALERTS:
        sent += 1
        notify(f"{short(h['symbol'])} alert {sent}/{ALERTS}",
               f"Profit {money(profit, cur, decimals=0)} is below {money(floor, cur, decimals=0)} (price {money(price, cur)})")
    elif not low:
        sent = 0
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "w") as f:
        f.write(str(sent))
    return low


def market_open(meta):
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    return period.get("start", 0) <= time.time() <= period.get("end", 0)


def menu_item(label, cmd=None, symbol=None, **extra):
    attrs = dict(extra)
    if cmd:
        attrs.update(bash=SELF, param1=cmd, terminal="false", refresh="true")
        if symbol:
            attrs["param2"] = symbol
    return label + (" | " + " ".join(f"{k}={v}" if " " not in str(v) else f'{k}="{v}"' for k, v in attrs.items()) if attrs else "")


def render():
    cfg = load()
    holdings = cfg.get("holdings", [])
    if not holdings:
        print("Stockbar")
        print("---")
        print(menu_item("Add stock…", "add"))
        return

    with ThreadPoolExecutor() as ex:
        metas = list(ex.map(quote, [h["symbol"] for h in holdings]))

    rows, totals, today_totals, any_low = [], {}, {}, False
    for h, meta in zip(holdings, metas):
        if not meta:
            rows.append((h, None))
            continue
        cur = meta.get("currency", "")
        price = meta["regularMarketPrice"]
        prev = meta.get("previousClose") or meta.get("chartPreviousClose") or price
        profit = (price - h["buy_price"]) * h["shares"]
        today = (price - prev) * h["shares"]
        low = check_alert(h, profit, price, cur)
        any_low |= low
        totals[cur] = totals.get(cur, 0) + profit
        today_totals[cur] = today_totals.get(cur, 0) + today
        rows.append((h, dict(meta=meta, cur=cur, price=price, prev=prev, profit=profit, today=today, low=low)))

    def color(r):
        return RED if r["low"] or (r["profit"] < 0 and r["h"].get("alert_below") is None) else GREEN

    for h, r in rows:
        if r:
            r["h"] = h

    pinned = cfg.get("pinned")
    if pinned == "TOTAL":
        label = "  ".join(money(v, c, sign=True, decimals=0) for c, v in totals.items())
        title_color = RED if any_low or any(v < 0 for v in totals.values()) else GREEN
        print(f"P&L {label} | color={title_color}")
    else:
        h, r = next(((h, r) for h, r in rows if h["symbol"] == pinned), rows[0])
        if r:
            print(f"{short(h['symbol'])} {money(r['price'], r['cur'])} · P&L {money(r['profit'], r['cur'], decimals=0)} | color={color(r)}")
        else:
            print(f"{short(h['symbol'])} ⚠︎")

    print("---")
    for h, r in rows:
        sym = h["symbol"]
        pin_mark = "✓ " if sym == pinned else ""
        if not r:
            print(f"{pin_mark}{short(sym)}  couldn't load price")
            print(menu_item("--Remove", "remove", sym))
            continue
        cur, meta = r["cur"], r["meta"]
        pct = (r["price"] - r["prev"]) / r["prev"] * 100 if r["prev"] else 0
        arrow = "▲" if pct >= 0 else "▼"
        print(f"{pin_mark}{short(sym)}  {money(r['price'], cur)}  {arrow}{abs(pct):.2f}%  ·  P&L {money(r['profit'], cur, sign=True, decimals=0)} | color={color(r)}")
        print(f"--{h.get('name') or meta.get('longName') or sym} ({meta.get('fullExchangeName', '')})")
        print(f"--Profit: {money(r['profit'], cur, sign=True)} on {h['shares']:g} shares @ {money(h['buy_price'], cur)} | color={color(r)}")
        print(f"--Today: {money(r['today'], cur, sign=True)} ({pct:+.2f}%)")
        alert = h.get("alert_below")
        print(f"--Alert below: {money(alert, cur, decimals=0) if alert is not None else 'off'}")
        print(f"--Day range: {money(meta.get('regularMarketDayLow', 0), cur)} – {money(meta.get('regularMarketDayHigh', 0), cur)}")
        status = "market open" if market_open(meta) else "market closed"
        print(f"--Last trade: {datetime.fromtimestamp(meta['regularMarketTime']).strftime('%d %b %H:%M')} ({status})")
        print("-----")
        if sym != pinned:
            print(menu_item("--Show in menu bar", "pin", sym))
        print(menu_item("--Edit shares, price, alert…", "edit", sym))
        print(menu_item("--Open on Yahoo Finance", href=f"https://finance.yahoo.com/quote/{sym}"))
        print(menu_item("--Remove", "remove", sym))

    print("---")
    for cur, v in totals.items():
        print(f"Total P&L: {money(v, cur, sign=True)}   Today: {money(today_totals[cur], cur, sign=True)}")
    if pinned != "TOTAL":
        print(menu_item("Show total P&L in menu bar", "pin", "TOTAL"))
    print(menu_item("Add stock…", "add"))
    print(menu_item("Edit config file", bash="/usr/bin/open", param1="-t", param2=CONFIG, terminal="false"))
    print(menu_item("Refresh", refresh="true"))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action(*sys.argv[1:3])
    else:
        render()
