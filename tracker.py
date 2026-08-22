#!/usr/bin/env python3

"""
Renae Upload Tracker

Checks the 10 public Instagram/TikTok accounts and attempts to count
uploads within a rolling 24-hour window.

If reliable timestamps cannot be obtained, the account is marked
UNVERIFIED instead of incorrectly reporting zero uploads.

Usage:
    python tracker.py
    python tracker.py --date 2026-08-21
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; RenaeUploadTracker/1.0)"


def fetch(url):
    """Fetch a public profile page."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "ignore")


def parse_epoch_values(html):
    """
    Extract timestamp-like values from public page HTML.

    Returns a list of UTC datetime objects.
    """
    values = []

    patterns = [
        r'"(?:createTime|create_time|timestamp|datePublished|uploadDate)"\s*:\s*"?(\\d{9,13})',
        r'"(?:createTime|create_time|timestamp|datePublished|uploadDate)"\s*:\s*(\d{9,13})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html)

        for value in matches:
            try:
                timestamp = int(value)

                # Convert milliseconds to seconds.
                if timestamp > 10**11:
                    timestamp = timestamp / 1000

                date = datetime.fromtimestamp(
                    timestamp,
                    timezone.utc,
                )

                values.append(date)

            except (ValueError, OverflowError, OSError):
                continue

    return sorted(set(values), reverse=True)


def check_account(account, target_date=None):
    """
    Check one account.

    If target_date is provided, check that UTC calendar day.
    Otherwise check the previous rolling 24 hours.
    """

    now = datetime.now(timezone.utc)

    if target_date:
        start = datetime.fromisoformat(target_date).replace(
            tzinfo=timezone.utc
        )

        end = start + timedelta(days=1)

    else:
        end = now
        start = now - timedelta(hours=24)

    try:
        html = fetch(account["url"])

        timestamps = parse_epoch_values(html)

        # No reliable timestamps available.
        if not timestamps:
            return {
                "status": "UNVERIFIED",
                "count": None,
                "times": [],
            }

        uploads = [
            timestamp
            for timestamp in timestamps
            if start <= timestamp < end
        ]

        count = len(uploads)

        return {
            "status": "PASS" if count >= 3 else "BEHIND",
            "count": count,
            "times": [
                timestamp.isoformat()
                for timestamp in uploads
            ],
        }

    except Exception as error:
        return {
            "status": "UNVERIFIED",
            "count": None,
            "times": [],
            "error": type(error).__name__,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Check Renae Erica social accounts."
    )

    parser.add_argument(
        "--date",
        help="Check a specific UTC date, e.g. 2026-08-21",
    )

    args = parser.parse_args()

    # Load account configuration.
    with open(
        "accounts.json",
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)

    accounts = config["accounts"]

    results = []

    print("=" * 80)
    print("RENAE UPLOAD TRACKER")
    print("=" * 80)

    if args.date:
        print(f"Checking date: {args.date}")
    else:
        print("Checking previous rolling 24 hours")

    print("=" * 80)

    for account in accounts:

        result = check_account(
            account,
            args.date,
        )

        combined_result = {
            **account,
            **result,
        }

        results.append(combined_result)

        count = (
            str(result["count"])
            if result["count"] is not None
            else "-"
        )

        print(
            f'{account["owner"]:8} '
            f'{account["platform"]:9} '
            f'@{account["username"]:25} '
            f'{result["status"]:12} '
            f'{count}'
        )

        # Small delay between accounts.
        time.sleep(0.5)

    # Make results directory if it doesn't exist.
    os.makedirs(
        "results",
        exist_ok=True,
    )

    # Create a safe filename.
    if args.date:
        filename = f"{args.date}.json"
    else:
        filename = (
            datetime.now(timezone.utc)
            .strftime("%Y-%m-%dT%H-%M-%SZ.json")
        )

    output_path = os.path.join(
        "results",
        filename,
    )

    output = {
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "target_date": args.date,

        "required_uploads": config.get(
            "required_uploads",
            3,
        ),

        "window_hours": config.get(
            "window_hours",
            24,
        ),

        "results": results,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 80)
    print(f"Results saved to: {output_path}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
