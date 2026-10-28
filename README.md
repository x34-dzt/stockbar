# Stockbar

Live stock prices and your P&L in the macOS menu bar, with alerts when profit drops below a number you pick.

```
RELIANCE ₹1,178.00 · P&L ₹1,280
```

- Any stock Yahoo Finance lists: NSE/BSE (`RELIANCE.NS`), US (`AAPL`), ETFs, indices.
- Shows your profit from shares × buy price, in green, or red once it falls below your alert.
- Sends 5 notifications when profit crosses below the alert, then stays quiet until it recovers.
- Add, edit, remove and pin stocks from the menu, or show total P&L instead of one stock.
- Refreshes every 5 seconds. One Python file, standard library only.

## Install

Needs macOS, Python 3 (ships with the Xcode command line tools) and [SwiftBar](https://github.com/swiftbar/SwiftBar).

```sh
git clone https://github.com/<you>/stockbar.git
cd stockbar
./install.sh
```

`install.sh` installs SwiftBar with Homebrew if it is missing, points it at `plugin/` and starts it.
Then click **Stockbar → Add stock…** in the menu bar.

## Configure

Holdings live in `~/.config/stockbar/holdings.json`, outside the repo:

```json
{
  "pinned": "RELIANCE.NS",
  "holdings": [
    {"symbol": "RELIANCE.NS", "shares": 10, "buy_price": 1050, "alert_below": 1000},
    {"symbol": "AAPL", "shares": 2, "buy_price": 150, "alert_below": null}
  ]
}
```

`pinned` is the symbol shown in the menu bar, or `"TOTAL"` for total P&L. `alert_below` is a profit
amount; set it to `null` for no alert.

To change the refresh rate, rename the plugin: `stockbar.5s.py` → `stockbar.30s.py` or `stockbar.1m.py`.

If notifications don't show, allow them for Script Editor in System Settings → Notifications.

## Notes

Prices come from Yahoo Finance's public chart endpoint, which needs no API key and can lag the exchange
by a few seconds. This is not investment advice and not a trading tool.

## License

MIT
