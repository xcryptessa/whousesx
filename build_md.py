#!/usr/bin/env python3

import json
import os
from datetime import datetime

# --- Configuration ---
INPUT_JSON = "twitter_tracking.json"
OUTPUT_MD = "WHO_USES_X.md"


def format_date(iso_str):
    """Converts ISO timestamp to readable YYYY-MM-DD format."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso_str


def generate_markdown():
    # 1. Load Data
    if not os.path.exists(INPUT_JSON):
        print(f"Error: {INPUT_JSON} not found.")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Group Data by Category
    # Structure: { "Retail": { "active": [], "removed": [] } }
    grouped_data = {}

    for item in data:
        category = item.get("Category", "Uncategorized")

        if category not in grouped_data:
            grouped_data[category] = {"active": [], "removed": []}

        if item.get("Currently Listed", False):
            grouped_data[category]["active"].append(item)
        else:
            if item.get("Account Handle", None) is not None:
                grouped_data[category]["removed"].append(item)

    # 3. Build Markdown Content
    lines = []
    lines.append("# Who Uses X?")
    lines.append(f"\n_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append(
        "\nA list of companies and organizations verifying their presence on X (formerly Twitter)."
    )
    lines.append("\n---")

    # Sort categories alphabetically
    sorted_categories = sorted(grouped_data.keys())

    for category in sorted_categories:
        cat_data = grouped_data[category]

        # Only print category if there is data
        if not cat_data["active"] and not cat_data["removed"]:
            continue

        lines.append(f"\n## {category}")

        # --- Active Table ---
        if cat_data["active"]:
            # Sort by Display Name
            sorted_active = sorted(cat_data["active"], key=lambda x: x["Display Name"])

            lines.append("\n| Display Name | X Handle | Last Seen |")
            lines.append("| :--- | :--- | :--- |")

            for item in sorted_active:
                name = item["Display Name"]
                url = item["URL"]
                handle = item.get("Account Handle", "N/A")
                last_seen = format_date(item.get("Last Seen"))

                # Format handle as link if it exists and looks like a handle
                handle_link = handle
                if handle and handle.startswith("@"):
                    clean_handle = handle[1:]  # Remove @
                    handle_link = f"[{handle}](https://x.com/{clean_handle})"

                lines.append(f"| [{name}]({url}) | {handle_link} | {last_seen} |")

        # --- Removed Table ---
        if cat_data["removed"]:
            # Sort by Display Name
            sorted_removed = sorted(
                cat_data["removed"], key=lambda x: x["Display Name"]
            )

            lines.append("\n### X Account Removed")
            lines.append("\n| Display Name | Last Known Handle | Last Seen |")
            lines.append("| :--- | :--- | :--- |")

            for item in sorted_removed:
                name = item["Display Name"]
                url = item["URL"]
                handle = item.get("Account Handle", "N/A")
                last_seen = format_date(item.get("Last Seen"))

                lines.append(f"| [{name}]({url}) | {handle} | {last_seen} |")

    # 4. Write to File
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Successfully generated {OUTPUT_MD}")


if __name__ == "__main__":
    generate_markdown()
