# Trakheesi Playwright Workers

Distributed web scraping system for Dubai Land Department Trakheesi data using Playwright with stealth mode.

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium
```

## Usage

### Quick Start (Recommended)

```bash
# Run 5 workers with live monitoring
uv run python master.py

# Run with visible browser windows
uv run python master.py --visible

# Run 3 workers
uv run python master.py -n 3
```

### First Run

On first run, if no browser profile exists, a Chromium window will open. You can configure the browser (e.g., accept cookies, adjust settings) or simply close it. The profile is saved and reused for all workers.

### Master Process Options

| Option | Description |
|--------|-------------|
| `-n N`, `--workers N` | Number of workers (default: 5) |
| `--visible` | Show browser windows |
| `--restart-threshold N` | Min total jobs before checking restart (default: 100) |
| `--min-rate N` | Min success rate % before restart (default: 80.0) |

### Auto-Restart

Workers are automatically restarted when:
- Total jobs processed >= `--restart-threshold`
- Success rate < `--min-rate`

This helps maintain high throughput when anti-bot detection kicks in.

### Monitoring

The master process displays a live stats table:

```
=== Trakheesi Master ===
Time: 17:30:00  |  Elapsed: 5m 30s
Auto-restart: total >= 100 AND rate < 80.0%

Worker | Success | Failed | Total | Rate   | Jobs/min | Restarts
-------|---------|--------|-------|--------|----------|----------
W1     |     100 |      2 |   102 |  98.0% |      8.5 | 0
W2     |      98 |      1 |    99 |  99.0% |      8.2 | 1
...
TOTAL  |     490 |      8 |   498 |  98.4% |     41.5 | 1

Running workers: 5/5
```

### Stopping

Press `Ctrl+C` to gracefully stop all workers. This will:
- Kill all worker processes
- Remove worker profile directories
- Keep the master profile intact

## Manual Worker Control

If you prefer to manage workers manually:

```bash
# Start a single worker
uv run python trakheesi_worker.py --profile --worker-id 1 --visible

# Monitor with shell script
watch ./monitor_workers.sh

# Kill all workers
pkill -f trakheesi_worker
```

### Worker Options

| Option | Description |
|--------|-------------|
| `--profile` | Use persistent browser profile |
| `--worker-id N` | Worker ID (creates separate profile) |
| `--visible` | Show browser window |
| `--browser TYPE` | chromium, firefox, or webkit |
| `--interval N` | Poll interval in seconds (default: 5) |
| `--restart-every N` | Restart browser every N jobs (default: 5) |

## Directory Structure

```
.
├── master.py              # Master process (recommended)
├── trakheesi_worker.py    # Worker script
├── monitor_workers.sh     # Manual monitoring script
├── data/
│   ├── trakheesi_browser_profile/    # Master profile
│   └── trakheesi_browser_profile_N/  # Worker profiles (auto-created)
└── logs/
    └── worker_N.log       # Worker logs
```
