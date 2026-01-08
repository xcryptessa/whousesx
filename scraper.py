#!/usr/bin/env python3

import csv
import json
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# --- Configuration ---
INPUT_CSV = "sites.csv"
OUTPUT_JSON = "twitter_tracking.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}


def get_timestamp():
    return datetime.now().isoformat()


def extract_handle_from_html(html_content):
    """
    Parses raw HTML content to find Twitter/X handles.
    Shared logic used by both Requests and Playwright methods.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links = soup.find_all("a", href=True)

    twitter_pattern = re.compile(
        r"https?://(?:www\.)?(?:twitter\.com|x\.com)/(?!intent|search|hashtag|home|explore|notifications|messages)([^/?#]+)",
        re.IGNORECASE,
    )

    for link in links:
        href = link["href"]
        match = twitter_pattern.search(href)
        if match:
            return f"@{match.group(1)}"

    return None


def check_url_fast(url):
    """
    Fast method: Uses requests to fetch static HTML.
    Returns the handle if found, or None if not found/error.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        # We don't raise_for_status here because a 403 might just mean we need Playwright
        if response.status_code == 200:
            return extract_handle_from_html(response.text)
    except Exception as e:
        # Silently fail on requests errors and let Playwright try
        pass
    return None


def extract_twitter_handle_playwright(url, browser):
    """
    Slow method: Uses Playwright with Stealth to render JS and lazy-loaded content.
    """
    page = browser.new_page()

    page.set_extra_http_headers(HEADERS)

    # Apply Stealth
    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    try:
        # Go to page
        page.goto(url, timeout=45000, wait_until="domcontentloaded")

        # Scroll logic
        for i in range(5):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(200)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

        # Get content and parse
        content = page.content()
        return extract_handle_from_html(content)

    except Exception as e:
        print(f"    Playwright Error: {e}")
        return None
    finally:
        page.close()


def load_existing_data(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def main():
    data = load_existing_data(OUTPUT_JSON)
    data_map = {item["URL"]: item for item in data}

    try:
        with open(INPUT_CSV, mode="r", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)

            # Pre-launch Playwright but don't create context yet
            # We want the browser ready IF we need it, but we won't use it for everything
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                print("Processing URLs...")

                for row in reader:
                    display_name = row["Display Name"]
                    category = row["Category"]
                    target_url = row["URL"]

                    print(f"Checking: {display_name} ... ", end="", flush=True)

                    # --- STRATEGY 1: FAST PASS ---
                    found_handle = check_url_fast(target_url)
                    method_used = "requests"

                    # --- STRATEGY 2: SLOW FALLBACK ---
                    if not found_handle:
                        # If fast pass failed, try the heavy browser
                        found_handle = extract_twitter_handle_playwright(
                            target_url, browser
                        )
                        method_used = "playwright"

                    current_time = get_timestamp()

                    # Logic to update JSON
                    if target_url in data_map:
                        record = data_map[target_url]
                        record["Display Name"] = display_name
                        record["Category"] = category

                        if found_handle:
                            record["Account Handle"] = found_handle
                            record["Last Seen"] = current_time
                            record["Currently Listed"] = True

                            if not record["First Seen"]:
                                record["First Seen"] = current_time

                            print(f"Found {found_handle} ({method_used})")
                        else:
                            record["Currently Listed"] = False
                            print(f"Not found.")

                    else:
                        new_record = {
                            "Display Name": display_name,
                            "Category": category,
                            "URL": target_url,
                            "Account Handle": found_handle,
                            "First Seen": current_time if found_handle else None,
                            "Last Seen": current_time if found_handle else None,
                            "Currently Listed": bool(found_handle),
                        }

                        data.append(new_record)
                        data_map[target_url] = new_record
                        print(f"New record: {found_handle} ({method_used})")

                browser.close()

    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_CSV}")
        return

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"\nProcessing complete. Data saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
