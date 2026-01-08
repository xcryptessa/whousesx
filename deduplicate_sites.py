#!/usr/bin/env python3

import pandas as pd
import os

INPUT_FILE = 'sites.csv'

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    # 1. Read the CSV
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Original record count: {len(df)}")

    # 2. Deduplicate
    # subset=['URL'] ensures we only look at the URL column for duplicates
    # keep='first' ensures we keep the top-most row and discard later ones
    df_deduped = df.drop_duplicates(subset=['URL'], keep='first')

    duplicates_removed = len(df) - len(df_deduped)

    # 3. Save back to CSV
    if duplicates_removed > 0:
        df_deduped.to_csv(INPUT_FILE, index=False)
        print(f"Success! Removed {duplicates_removed} duplicate URLs.")
        print(f"New record count: {len(df_deduped)}")
    else:
        print("No duplicates found. File is already clean.")

if __name__ == "__main__":
    main()
