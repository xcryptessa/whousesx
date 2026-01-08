#!/usr/bin/env python3

import csv
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# --- Configuration ---
INPUT_CSV = "sites.csv"
OUTPUT_JSON = "twitter_tracking.json"
MAX_WORKERS = 20  # Number of parallel threads for the fast pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-NZ;q=0.9,en-AU;q=0.8,en;q=0.7,en-US;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "sec-ch-ua": '"Chromium";v="143", "Google Chrome";v="143", "Not-A.Brand";v="99"',
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


def check_url_fast(row):
    """
    Thread-safe worker function.
    Returns: (row, handle_found_or_None)
    """
    url = row["URL"]
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        # We don't raise_for_status here because a 403 might just mean we need Playwright
        if response.status_code == 200:
            handle = extract_handle_from_html(response.text)
            return (row, handle)
    except Exception:
        pass

    return (row, None)


def extract_twitter_handle_playwright(url, browser):
    """
    Slow method: Uses Playwright with Stealth.
    """
    page = browser.new_page()
    page.set_extra_http_headers(HEADERS)

    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")

        # Scroll logic to trigger lazy loading
        for _ in range(3):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(200)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

        content = page.content()
        return extract_handle_from_html(content)

    except Exception as e:
        # print(f"    Playwright Error: {e}")
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


def should_process(record):
    """Returns False if record was updated < 24 hours ago."""
    last_seen = record.get("Last Seen")
    if last_seen:
        try:
            last_seen_dt = datetime.fromisoformat(last_seen)
            if datetime.now() - last_seen_dt < timedelta(hours=24):
                return False
        except ValueError:
            pass
    return True


def update_record(data_map, data_list, row, handle, method_used):
    """Helper to update the data structures cleanly."""
    target_url = row["URL"]
    display_name = row["Display Name"]
    category = row["Category"]
    current_time = get_timestamp()

    if target_url in data_map:
        record = data_map[target_url]
        record["Display Name"] = display_name
        record["Category"] = category

        if handle:
            record["Account Handle"] = handle
            record["Last Seen"] = current_time
            record["Currently Listed"] = True
            if not record.get("First Seen"):
                record["First Seen"] = current_time
            print(f"[SUCCESS] {display_name}: Found {handle} ({method_used})")
        else:
            record["Currently Listed"] = False
            print(f"[MISSING] {display_name}: No handle found ({method_used})")
    else:
        new_record = {
            "Display Name": display_name,
            "Category": category,
            "URL": target_url,
            "Account Handle": handle,
            "First Seen": current_time if handle else None,
            "Last Seen": current_time if handle else None,
            "Currently Listed": bool(handle),
        }
        data_list.append(new_record)
        data_map[target_url] = new_record
        if handle:
            print(f"[NEW] {display_name}: Found {handle} ({method_used})")
        else:
            print(f"[NEW] {display_name}: No handle found ({method_used})")


def main():
    # 1. Load Data
    data = load_existing_data(OUTPUT_JSON)
    data_map = {item["URL"]: item for item in data}

    rows_to_process = []

    # 2. Read CSV and Filter
    try:
        with open(INPUT_CSV, mode="r", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                url = row["URL"]
                if url in data_map and not should_process(data_map[url]):
                    # print(f"Skipping {row['Display Name']} (Recent)")
                    continue
                rows_to_process.append(row)
    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_CSV}")
        return

    print(f"Queue size: {len(rows_to_process)} URLs to check.")

    # 3. PHASE 1: Fast Pass (Multi-threaded)
    print("\n--- Phase 1: Fast Pass (Requests) ---")
    needs_playwright = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all jobs
        future_to_row = {
            executor.submit(check_url_fast, row): row for row in rows_to_process
        }

        for future in as_completed(future_to_row):
            row, handle = future.result()

            if handle:
                # Success! Update data immediately
                update_record(data_map, data, row, handle, "requests")
            else:
                # Failed fast pass, add to slow queue
                needs_playwright.append(row)

    # 4. PHASE 2: Slow Pass (Playwright)
    if needs_playwright:
        print(
            f"\n--- Phase 2: Slow Pass (Playwright) - {len(needs_playwright)} items ---"
        )

        with sync_playwright() as p:
            # We run ONE browser instance to save memory, processing tabs sequentially
            browser = p.chromium.launch(headless=True)

            for row in needs_playwright:
                print(f"Checking: {row['Display Name']}...", end=" ", flush=True)
                handle = extract_twitter_handle_playwright(row["URL"], browser)

                # Update record regardless of result (to mark as checked/not found)
                if handle:
                    print(f"FOUND: {handle}")
                    update_record(data_map, data, row, handle, "playwright")
                else:
                    print("Not found.")
                    update_record(data_map, data, row, None, "playwright")

            browser.close()

    # 5. Save Data
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"\nProcessing complete. Data saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
