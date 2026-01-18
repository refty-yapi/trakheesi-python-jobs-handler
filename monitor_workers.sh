#!/bin/bash
# Monitor trakheesi workers - cumulative stats

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

echo "=== Trakheesi Workers Monitor ==="
echo "Time: $(date '+%H:%M:%S')"
echo ""

total_success=0
total_fail=0
total_jobs_per_min=0

echo "Worker | Success | Failed | Total | Rate   | Jobs/min"
echo "-------|---------|--------|-------|--------|----------"

for i in 1 2 3 4 5; do
  log="$LOGS_DIR/worker_$i.log"
  if [ -f "$log" ]; then
    s=$(grep -c '✓' "$log" 2>/dev/null)
    [ -z "$s" ] && s=0
    f=$(grep -c '✗' "$log" 2>/dev/null)
    [ -z "$f" ] && f=0
    total=$((s + f))

    # Calculate jobs per minute based on log file age
    if [ "$total" -gt 0 ]; then
      rate=$(awk "BEGIN {printf \"%.1f\", $s * 100 / $total}")
      # Get file creation time (macOS uses stat -f, Linux uses stat -c)
      if [[ "$OSTYPE" == "darwin"* ]]; then
        file_created=$(stat -f %B "$log" 2>/dev/null)
      else
        file_created=$(stat -c %W "$log" 2>/dev/null)
        [ "$file_created" = "0" ] && file_created=$(stat -c %Y "$log" 2>/dev/null)
      fi
      now=$(date +%s)
      elapsed_sec=$((now - file_created))
      if [ "$elapsed_sec" -gt 0 ]; then
        jobs_per_min=$(awk "BEGIN {printf \"%.1f\", $total * 60 / $elapsed_sec}")
      else
        jobs_per_min="0.0"
      fi
    else
      rate="0.0"
      jobs_per_min="0.0"
    fi

    printf "W%-5d | %7d | %6d | %5d | %5s%% | %s\n" "$i" "$s" "$f" "$total" "$rate" "$jobs_per_min"
    total_success=$((total_success + s))
    total_fail=$((total_fail + f))
  fi
done

echo "-------|---------|--------|-------|--------|----------"
grand_total=$((total_success + total_fail))

# Calculate total jobs per minute from first log file
if [ "$grand_total" -gt 0 ]; then
  grand_rate=$(awk "BEGIN {printf \"%.1f\", $total_success * 100 / $grand_total}")
  # Use earliest log file for total rate
  first_log="$LOGS_DIR/worker_1.log"
  if [ -f "$first_log" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      file_created=$(stat -f %B "$first_log" 2>/dev/null)
    else
      file_created=$(stat -c %W "$first_log" 2>/dev/null)
      [ "$file_created" = "0" ] && file_created=$(stat -c %Y "$first_log" 2>/dev/null)
    fi
    now=$(date +%s)
    elapsed_sec=$((now - file_created))
    elapsed_min=$((elapsed_sec / 60))
    if [ "$elapsed_sec" -gt 0 ]; then
      total_jobs_per_min=$(awk "BEGIN {printf \"%.1f\", $grand_total * 60 / $elapsed_sec}")
    else
      total_jobs_per_min="0.0"
    fi
  fi
else
  grand_rate="0.0"
  total_jobs_per_min="0.0"
  elapsed_min=0
fi

printf "TOTAL  | %7d | %6d | %5d | %5s%% | %s\n" "$total_success" "$total_fail" "$grand_total" "$grand_rate" "$total_jobs_per_min"

echo ""
echo "Running workers: $(ps aux | grep 'trakheesi_worker' | grep -v 'uv run' | grep -v grep | wc -l | tr -d ' ')"
[ "$elapsed_min" -gt 0 ] && echo "Elapsed: ${elapsed_min}m"
