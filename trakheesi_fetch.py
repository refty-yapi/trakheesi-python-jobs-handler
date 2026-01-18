"""
Fetch property listing data from Dubai Land Department Trakheesi system.
Uses Playwright in stealth mode to intercept API responses.
"""

import asyncio
import json
from playwright.async_api import async_playwright, Response
from playwright_stealth import Stealth


async def fetch_trakheesi_listing(listing_guid: str, headless: bool = True) -> dict | None:
    """
    Fetch listing data from Trakheesi validation page.

    Args:
        listing_guid: The listing GUID from the URL parameter (khevJujtDig)
        headless: Run browser in headless mode (default: True)

    Returns:
        dict with listing data or None if failed
    """
    url = f"https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation?khevJujtDig={listing_guid}"
    api_response_data = None

    async def handle_response(response: Response):
        nonlocal api_response_data
        if "/trakheesi/" in response.url and response.status == 200:
            try:
                api_response_data = await response.json()
            except:
                pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        # Apply stealth patches
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        # Listen for API responses
        page.on("response", handle_response)

        # Navigate and wait for network to settle
        await page.goto(url, wait_until="domcontentloaded")

        # Wait for the page to load and make API call
        await page.wait_for_timeout(5000)

        # If no data yet, wait for network idle
        if not api_response_data:
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

        await browser.close()

    return api_response_data


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Trakheesi listing data")
    parser.add_argument(
        "guid",
        nargs="?",
        default="7w5cpibu2sz63kuozlp1rfhyhphj2wxyecsjazcifymqvkzvl",
        help="Listing GUID (khevJujtDig parameter)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window (non-headless)"
    )

    args = parser.parse_args()

    print(f"Fetching listing: {args.guid}...")

    data = await fetch_trakheesi_listing(args.guid, headless=not args.visible)

    if data:
        if args.pretty:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(data, ensure_ascii=False))
    else:
        print("Failed to fetch listing data")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
