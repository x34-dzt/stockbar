#!/bin/sh
set -e
cd "$(dirname "$0")"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
[ -d /Applications/SwiftBar.app ] || brew install --cask swiftbar
chmod +x plugin/*.py
defaults write com.ameba.SwiftBar PluginDirectory "$PWD/plugin"
osascript -e 'quit app "SwiftBar"' 2>/dev/null || true
sleep 1
open -a SwiftBar
echo "Stockbar is running. Click it in the menu bar, then Add stock…"
