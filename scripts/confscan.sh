#!/bin/bash
# Confidentiality sanity scan for the public site. Run before every push:
#   bash scripts/confscan.sh
# Flags anything that should be redacted on backtests.html / strategies.html /
# *.ai.txt. Allowed/expected hits: the headline ratio 50/30/20, the viewport
# meta initial-scale=1, embedded JS slider vars, and metric-label fragments in
# the .ai.txt (Tail=/Sharpe=/Omega= etc.). Anything else -> redact in
# glossary._BT_PUBLIC / _bt_redact and rebuild. See AI_PROCEDURES/WEBSITE_DEPLOY.md.
cd "$(dirname "$0")/../docs" || exit 1
for f in backtests.html strategies.html strategies.ai.txt; do
  [ -f "$f" ] || continue
  echo "============ $f ============"
  echo "--- dollar amounts ---"; grep -oE '\$[0-9][0-9,.]+' "$f" | sort -u | head
  echo "--- tickers ---"; grep -oE '\b(SPY|QQQ|IEF|GLD|XAUUSD|XAGUSD|EURUSD|USDJPY|GBPUSD|EURJPY|GBPJPY|EFA|EEM|DIA|IWM|EWW|DBC|XLK|XLF|SLV|NAFTRAC|SOXX|VGT|VUG)\b' "$f" | sort | uniq -c | sort -rn | head -30
  echo "--- param=value / thresholds / weights ---"; grep -oE '[a-z_]+=[0-9.]+|[0-9.]+sigma|[0-9]{2,3}-EMA|[0-9]{2,3} ?EMA|SMA[0-9]{2,3}|[0-9]+R\b|[0-9]+/[0-9]+/[0-9]+' "$f" | sort -u | head -40
  echo "--- internal paths / repos ---"; grep -oiE 'Trading_Index|SignalLib|/home/|C:..Users|Downloads|REPORT\.md|/mnt/c' "$f" | sort -u | head
  echo
done
