# Who Uses X?

Given recent news about X, Grok, and Elon Musk, here is a list of companies across various industries that are using X/Twitter.

**[See The List](https://github.com/xcryptessa/whousesx/blob/main/WHO_USES_X.md)**

## Why?

Based on your own ethics, you may wish to be aware of the values of the companies you do business with, and who they are dedicating time, space on their homepage, and effort to support.

## Data Collection

The main script, `scraper.py`, reads a list of target websites from a CSV file. For each site, it performs the following logic:

1. **Access:** It visits the provided homepage URL.
2. **Scrape:** It scans the HTML for outgoing links to `twitter.com` or `x.com`.
3. **Validate:** It ignores share buttons (e.g., `/intent/tweet`) and looks specifically for profile links.
4. **Update Database:**
* If a link is found, it records the handle and updates the `Last Seen` timestamp.
* If a link was previously found but is now missing, it sets the `Currently Listed` flag to `false`.
* If the site is new, it adds a `First Seen` timestamp.

### Running Locally

The script uses Python 3.14, and `pipenv` to manage dependencies. To run this locally, you simply need to:

1. **Install Dependencies:**
Run the following command in the project root to install the dependencies.

```bash
pipenv install
playwright install
```

2. **Run the Scraper:**
You can execute the script within the virtual environment using:
```bash
pipenv run python scraper.py
```

## The Data

The collected data is stored in `twitter_tracking.json`. It provides a historical record of when a link was first observed and when it was last verified.

```json
[
    {
        "Display Name": "OpenAI",
        "Category": "AI Research",
        "URL": "https://openai.com",
        "Account Handle": "@OpenAI",
        "First Seen": "2023-10-27T10:00:00.000000",
        "Last Seen": "2024-01-15T14:30:00.000000",
        "Currently Listed": true
    },
    {
        "Display Name": "Legacy Corp",
        "Category": "Retail",
        "URL": "https://example-legacy.com",
        "Account Handle": "@LegacyCorp",
        "First Seen": "2023-09-01T09:00:00.000000",
        "Last Seen": "2023-11-05T11:20:00.000000",
        "Currently Listed": false
    }
]

```

## Adding Companies

The list of companies to track is stored in `sites.csv`. If you wish to add more entities to the tracker, append them to this file using the following format:

```csv
Display Name,Category,URL
Target,Retail,https://target.com/
PBS,Media,https://www.pbs.org/

```
