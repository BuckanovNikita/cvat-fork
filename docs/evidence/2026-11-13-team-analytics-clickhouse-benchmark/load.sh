#!/usr/bin/env bash
# Load synthetic events month by month. usage: load.sh [first_month_index last_month_index]
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
bounds=(2025-11-14 2025-12-01 2026-01-01 2026-02-01 2026-03-01 2026-04-01 2026-05-01 2026-06-01
        2026-07-01 2026-08-01 2026-09-01 2026-10-01 2026-11-01 2026-11-14)
first="${1:-0}"; last="${2:-12}"
for ((m = first; m <= last; m++)); do
  a="${bounds[$m]}"; b="${bounds[$((m + 1))]}"
  s=$(date +%s.%N)
  "$D/ch.sh" "$D/03_gen_events.sql" --param_d_from="$a" --param_d_to="$b"
  e=$(date +%s.%N)
  echo "loaded $a..$b in $(echo "$e - $s" | bc) s"
done
