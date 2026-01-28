"""
Trakheesi job worker - fetches jobs from API, scrapes data, submits results.
Reuses browser instance for efficiency.
"""

import asyncio
import json
import shutil
import sys
import httpx
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth

JOBS_API = "https://jobs-api.refty.ai/trakheesi/job"
RESULTS_API = "https://jobs-api.refty.ai/trakheesi/job/result"

# Persistent browser profile directory
from pathlib import Path
BASE_PROFILE_DIR = Path(__file__).parent / "data" / "trakheesi_browser_profile"



def get_profile_dir(worker_id: int | None) -> Path:
    """Get profile directory for a worker. Copies base profile if needed."""
    if worker_id is None:
        return BASE_PROFILE_DIR

    worker_profile = BASE_PROFILE_DIR.parent / f"trakheesi_browser_profile_{worker_id}"

    # Copy base profile to worker profile if base exists and worker doesn't
    if BASE_PROFILE_DIR.exists() and not worker_profile.exists():
        print(f"Copying base profile to worker {worker_id}...")
        shutil.copytree(BASE_PROFILE_DIR, worker_profile)

    return worker_profile


async def fetch_jobs(client: httpx.AsyncClient) -> list[dict]:
    """Fetch jobs from the API (long-polling)."""
    try:
        resp = await client.get(JOBS_API, timeout=120.0)  # Long timeout for long-polling
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "id" in data:
                return [data]
        elif resp.status_code == 304:
            return []  # No new jobs
    except httpx.ReadTimeout:
        return []  # Normal for long-polling
    except Exception as e:
        print(f"Error fetching jobs: {e}")
    return []


async def submit_result(client: httpx.AsyncClient, job_id: str, timestamp: int, response: dict) -> bool:
    """Submit job result back to API."""
    try:
        payload = {
            "id": job_id,
            "timestamp": timestamp,
            "response": response
        }
        resp = await client.post(RESULTS_API, json=payload)
        return resp.status_code == 200
    except Exception as e:
        print(f"Error submitting result: {e}")
        return False


async def scrape_listing(page: Page, listing_guid: str) -> dict | None:
    """Scrape a single listing using existing browser page."""
    url = f"https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation?khevJujtDig={listing_guid}"
    api_response_data = None

    async def handle_response(response):
        nonlocal api_response_data
        if "/trakheesi/" in response.url and response.status == 200:
            try:
                api_response_data = await response.json()
            except:
                pass

    page.on("response", handle_response)

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        if not api_response_data:
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Error scraping {listing_guid}: {e}")
    finally:
        page.remove_listener("response", handle_response)

    return api_response_data


async def run_worker(poll_interval: int = 5, headless: bool = True, browser_type: str = "chromium", restart_every: int = 5, use_profile: bool = False, worker_id: int | None = None, window_position: str | None = None):
    """Main worker loop."""
    restart_msg = f"restart every {restart_every}" if restart_every > 0 else "no restart"
    profile_msg = f"profile #{worker_id}" if use_profile and worker_id else ("with profile" if use_profile else "no profile")
    worker_label = f"[W{worker_id}] " if worker_id else ""
    print(f"{worker_label}Starting Trakheesi worker ({browser_type}, headless={headless}, {restart_msg}, {profile_msg})...")

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
        timeout=httpx.Timeout(30.0, read=120.0)  # Long read timeout for polling
    ) as client:
        async with async_playwright() as p:
            # Select browser launcher
            if browser_type == "firefox":
                browser_launcher = p.firefox
                browser_args = []
            elif browser_type == "webkit":
                browser_launcher = p.webkit
                browser_args = []
            else:
                browser_launcher = p.chromium
                browser_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--no-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--window-size=1280,800",
                ]
                if window_position:
                    browser_args.append(f"--window-position={window_position}")

            # Get profile directory for this worker
            profile_dir = get_profile_dir(worker_id) if use_profile else None

            async def create_browser():
                """Create a new browser instance with stealth."""
                if use_profile:
                    # Use persistent context (keeps login, cookies, etc.)
                    profile_dir.mkdir(parents=True, exist_ok=True)
                    context = await browser_launcher.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        headless=headless,
                        viewport={"width": 1280, "height": 800},
                        args=browser_args if browser_args else None,
                    )
                    page = context.pages[0] if context.pages else await context.new_page()
                    browser = None  # No separate browser object with persistent context
                else:
                    browser = await browser_launcher.launch(
                        headless=headless,
                        args=browser_args if browser_args else None,
                    )
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="en-US",
                        timezone_id="America/New_York",
                    )
                    page = await context.new_page()

                stealth = Stealth(
                    navigator_webdriver=True,
                    navigator_plugins=True,
                    navigator_permissions=True,
                    webgl_vendor=True,
                    chrome_runtime=True,
                )
                await stealth.apply_stealth_async(page)
                return browser, context, page

            browser, context, page = await create_browser()
            print(f"{worker_label}Browser ready. Polling for jobs...")
            if use_profile:
                print(f"{worker_label}Profile: {profile_dir}")

            jobs_processed = 0
            jobs_failed = 0
            jobs_since_restart = 0
            jobs_since_report = 0
            report_every = 10  # Report stats every N jobs

            while True:
                try:
                    jobs = await fetch_jobs(client)

                    if jobs:
                        print(f"\n{worker_label}📥 Got {len(jobs)} job(s)")

                        for job in jobs:
                            job_id = job.get("id")
                            if not job_id:
                                continue

                            # Restart browser every N jobs (if enabled, and not using profile)
                            if restart_every > 0 and jobs_since_restart >= restart_every and not use_profile:
                                print(f"\n🔄 Restarting browser...")
                                if browser:
                                    await browser.close()
                                else:
                                    await context.close()
                                await asyncio.sleep(2)
                                browser, context, page = await create_browser()
                                jobs_since_restart = 0
                                print("Browser restarted.")

                            timestamp = job.get("timestamp", int(asyncio.get_event_loop().time() * 1000))
                            print(f"  → {job_id[:30]}...", end=" ", flush=True)

                            # Scrape the listing
                            result = await scrape_listing(page, job_id)

                            if result:
                                # Submit result
                                success = await submit_result(client, job_id, timestamp, result)
                                if success:
                                    jobs_processed += 1
                                    jobs_since_restart += 1
                                    jobs_since_report += 1
                                    print(f"✓ ({jobs_processed})")
                                else:
                                    print("✗ submit failed")
                                    jobs_failed += 1
                                    jobs_since_report += 1
                            else:
                                print("✗ scrape failed")
                                jobs_failed += 1
                                jobs_since_restart += 1
                                jobs_since_report += 1

                            # Report stats periodically
                            if jobs_since_report >= report_every:
                                total = jobs_processed + jobs_failed
                                rate = (jobs_processed / total * 100) if total > 0 else 0
                                print(f"\n{worker_label}📊 Stats: {jobs_processed}/{total} ({rate:.1f}% success)")
                                jobs_since_report = 0

                            # Small delay between jobs
                            await asyncio.sleep(1)
                    else:
                        # No jobs, poll again
                        print(".", end="", flush=True)

                except KeyboardInterrupt:
                    total = jobs_processed + jobs_failed
                    rate = (jobs_processed / total * 100) if total > 0 else 0
                    print(f"\n\n📊 Final: {jobs_processed}/{total} ({rate:.1f}% success)")
                    break
                except Exception as e:
                    print(f"\nError: {e}")
                    await asyncio.sleep(poll_interval)

            if browser:
                await browser.close()
            else:
                await context.close()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Trakheesi job worker")
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window"
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        default="chromium",
        help="Browser to use (default: chromium)"
    )
    parser.add_argument(
        "--restart-every",
        type=int,
        default=5,
        help="Restart browser every N jobs (default: 5, 0 to disable)"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Use persistent browser profile (keeps login/cookies)"
    )
    parser.add_argument(
        "--worker-id",
        type=int,
        default=None,
        help="Worker ID for parallel execution (creates separate profile copy)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (redirects stdout)"
    )
    parser.add_argument(
        "--window-position",
        type=str,
        default=None,
        help="Window position as X,Y (e.g. 1920,0 for second monitor)"
    )

    args = parser.parse_args()

    # Redirect stdout to log file if specified
    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = open(log_path, "w", encoding="utf-8", buffering=1)  # Line buffered, UTF-8 for emoji
        sys.stderr = sys.stdout

    await run_worker(
        poll_interval=args.interval,
        headless=not args.visible,
        browser_type=args.browser,
        restart_every=args.restart_every,
        use_profile=args.profile,
        worker_id=args.worker_id,
        window_position=args.window_position,
    )


if __name__ == "__main__":
    asyncio.run(main())
