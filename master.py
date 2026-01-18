"""
Trakheesi Master Process - orchestrates workers with profile management and monitoring.
"""

import argparse
import asyncio
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

# Directories
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
LOGS_DIR = SCRIPT_DIR / "logs"
MASTER_PROFILE = DATA_DIR / "trakheesi_browser_profile"

# Global state for cleanup
worker_processes: list[subprocess.Popen] = []
num_workers = 0
running = True


async def setup_master_profile():
    """Check if master profile exists, if not launch browser for login."""
    if MASTER_PROFILE.exists():
        print(f"Master profile found: {MASTER_PROFILE}")
        return True

    print("No master profile found. Launching browser for login...")
    print("Please log in to the website, then close the browser window.")
    print()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(MASTER_PROFILE),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Navigate to the target site
        await page.goto("https://trakheesi.dubailand.gov.ae/")

        print("Browser opened. Close it when you're done logging in...")

        # Wait for browser to close
        try:
            while len(context.pages) > 0:
                await asyncio.sleep(1)
        except Exception:
            pass

        await context.close()

    print("Master profile saved.")
    return True


def clean_worker_profiles(n: int):
    """Remove existing worker profiles and logs."""
    print(f"Cleaning up {n} worker profiles and logs...")

    for i in range(1, n + 1):
        # Remove worker profile
        profile_dir = DATA_DIR / f"trakheesi_browser_profile_{i}"
        if profile_dir.exists():
            shutil.rmtree(profile_dir)

        # Remove worker log
        log_file = LOGS_DIR / f"worker_{i}.log"
        if log_file.exists():
            log_file.unlink()


def create_worker_profiles(n: int):
    """Copy master profile to worker profiles."""
    print(f"Creating {n} worker profiles...")

    for i in range(1, n + 1):
        worker_profile = DATA_DIR / f"trakheesi_browser_profile_{i}"
        print(f"  Copying to profile {i}...")
        shutil.copytree(MASTER_PROFILE, worker_profile)


def start_workers(n: int, visible: bool) -> list[subprocess.Popen]:
    """Start worker subprocesses."""
    global worker_processes

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    processes = []
    for i in range(1, n + 1):
        log_file = LOGS_DIR / f"worker_{i}.log"
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "trakheesi_worker.py"),
            "--profile",
            "--worker-id", str(i),
        ]
        if visible:
            cmd.append("--visible")

        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(SCRIPT_DIR),
            )
            processes.append(proc)
            print(f"  Started worker {i} (PID {proc.pid})")

    worker_processes = processes
    return processes


def parse_log_stats(log_file: Path) -> tuple[int, int, float]:
    """Parse log file for success/failure counts. Returns (success, failed, jobs_per_min)."""
    if not log_file.exists():
        return 0, 0, 0.0

    try:
        content = log_file.read_text()
        success = content.count("✓")
        failed = content.count("✗")
        total = success + failed

        if total > 0:
            # Calculate jobs per minute based on file creation time
            file_created = log_file.stat().st_birthtime
            elapsed_sec = time.time() - file_created
            if elapsed_sec > 0:
                jobs_per_min = total * 60 / elapsed_sec
            else:
                jobs_per_min = 0.0
        else:
            jobs_per_min = 0.0

        return success, failed, jobs_per_min
    except Exception:
        return 0, 0, 0.0


def display_stats(n: int, start_time: float):
    """Display monitoring stats table."""
    # Clear screen
    print("\033[2J\033[H", end="")

    elapsed_sec = time.time() - start_time
    elapsed_min = int(elapsed_sec // 60)
    elapsed_sec_rem = int(elapsed_sec % 60)

    print("=== Trakheesi Master ===")
    print(f"Time: {time.strftime('%H:%M:%S')}  |  Elapsed: {elapsed_min}m {elapsed_sec_rem}s")
    print()

    print("Worker | Success | Failed | Total | Rate   | Jobs/min")
    print("-------|---------|--------|-------|--------|----------")

    total_success = 0
    total_failed = 0

    for i in range(1, n + 1):
        log_file = LOGS_DIR / f"worker_{i}.log"
        success, failed, jobs_per_min = parse_log_stats(log_file)
        total = success + failed
        rate = (success * 100 / total) if total > 0 else 0.0

        print(f"W{i:<5} | {success:>7} | {failed:>6} | {total:>5} | {rate:>5.1f}% | {jobs_per_min:.1f}")

        total_success += success
        total_failed += failed

    print("-------|---------|--------|-------|--------|----------")

    grand_total = total_success + total_failed
    grand_rate = (total_success * 100 / grand_total) if grand_total > 0 else 0.0
    total_jobs_per_min = (grand_total * 60 / elapsed_sec) if elapsed_sec > 0 else 0.0

    print(f"TOTAL  | {total_success:>7} | {total_failed:>6} | {grand_total:>5} | {grand_rate:>5.1f}% | {total_jobs_per_min:.1f}")
    print()

    # Check running workers
    alive = sum(1 for p in worker_processes if p.poll() is None)
    print(f"Running workers: {alive}/{n}")
    print()
    print("Press Ctrl+C to stop all workers")


def cleanup():
    """Kill workers and remove worker profiles."""
    global running, worker_processes, num_workers

    running = False
    print("\n\nShutting down...")

    # Kill worker processes
    for proc in worker_processes:
        if proc.poll() is None:
            print(f"  Killing worker PID {proc.pid}...")
            proc.terminate()

    # Wait for processes to terminate
    for proc in worker_processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Remove worker profiles
    print("Removing worker profiles...")
    for i in range(1, num_workers + 1):
        profile_dir = DATA_DIR / f"trakheesi_browser_profile_{i}"
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
            print(f"  Removed profile {i}")

    print("Cleanup complete.")


def signal_handler(signum, frame):
    """Handle Ctrl+C."""
    cleanup()
    sys.exit(0)


async def main():
    global num_workers

    parser = argparse.ArgumentParser(description="Trakheesi Master Process")
    parser.add_argument(
        "-n", "--workers",
        type=int,
        default=5,
        help="Number of workers (default: 5)"
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser windows"
    )

    args = parser.parse_args()
    num_workers = args.workers

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Step 1: Ensure master profile exists
    await setup_master_profile()

    # Step 2: Clean and create worker profiles
    clean_worker_profiles(num_workers)
    create_worker_profiles(num_workers)

    # Step 3: Start workers
    print(f"\nStarting {num_workers} workers...")
    start_workers(num_workers, args.visible)

    # Step 4: Monitor loop
    print("\nMonitoring workers...")
    time.sleep(2)

    start_time = time.time()
    while running:
        display_stats(num_workers, start_time)
        time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
