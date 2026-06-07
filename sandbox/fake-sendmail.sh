#!/bin/sh
set -eu

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUT_DIR="/var/log/php-mail"
OUT="$OUT_DIR/mail-$(date -u +%Y%m%d-%H%M%S)-$$.eml"

mkdir -p "$OUT_DIR"

{
  echo "=== fake-sendmail captured at $TS ==="
  echo "Args: $*"
  echo
  cat -
  echo
} >> "$OUT"

chmod 600 "$OUT" 2>/dev/null || true
exit 0
