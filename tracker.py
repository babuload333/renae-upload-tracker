import os
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
import requests


# ============================================================
# SETTINGS
# ============================================================

REQUIRED_UPLOADS = 3
WINDOW_HOURS = 24

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

if not APIFY_TOKEN:
    raise RuntimeError("APIFY_TOKEN GitHub Secret is missing.")


ACCOUNTS = [
    # YOOO
    {
        "owner": "Yooo",
        "platform": "tiktok",
        "username": "renaeericacentral",
    },
    {
        "owner": "Yooo",
        "platform": "tiktok",
        "username": "renaeericavods",
    },
    {
        "owner": "Yooo",
        "platform": "instagram",
        "username": "renaeericacentral",
    },
    {
        "owner": "Yooo",
        "platform": "instagram",
        "username": "renaeericahub",
    },

    # PRUDHIV
    {
        "owner": "Prudhiv",
        "platform": "tiktok",
        "username": "renaeericatv",
    },
    {
        "owner": "Prudhiv",
        "platform": "tiktok",
        "username": "renaeericadaily",
    },
    {
        "owner": "Prudhiv",
        "platform": "instagram",
        "username": "renaeericatvx",
    },
    {
        "owner": "Prudhiv",
        "platform": "instagram",
        "username": "renaeericadaily",
    },

    # ANYA
    {
        "owner": "Anya",
        "platform": "instagram",
        "username": "renaeerica.fanpage",
    },
    {
        "owner": "Anya",
        "platform": "tiktok",
        "username": "renaeerica.fanpage",
    },
]


# ============================================================
# DATE
# ============================================================

def get_target_date():
    """
    Optional:
        python tracker.py 2026-08-21

    If no date is supplied, yesterday is used.
    """

    if len(sys.argv) > 1 and sys.argv[1].strip():
        return datetime.strptime(
            sys.argv[1].strip(),
            "%Y-%m-%d"
        ).date()

    return (
        datetime.now(timezone.utc).date()
        - timedelta(days=1)
    )


TARGET_DATE = get_target_date()

START_TIME = datetime.combine(
    TARGET_DATE,
    datetime.min.time(),
    tzinfo=timezone.utc
)

END_TIME = START_TIME + timedelta(hours=WINDOW_HOURS)


# ============================================================
# HELPERS
# ============================================================

def parse_datetime(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # TikTok timestamps are often Unix timestamps
        try:
            return datetime.fromtimestamp(
                value,
                tz=timezone.utc
            )
        except Exception:
            return None

    value = str(value).strip()

    if not value:
        return None

    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        pass

    # Common timestamp formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt
            ).replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def get_timestamp(item, platform):
    """
    Tries the timestamp fields used by TikTok and Instagram
    scrapers.
    """

    possible_fields = []

    if platform == "tiktok":
        possible_fields = [
            "createTime",
            "createTimeISO",
            "timestamp",
            "createdAt",
            "date",
            "publishedAt",
        ]

    else:
        possible_fields = [
            "timestamp",
            "takenAt",
            "takenAtTimestamp",
            "createdAt",
            "date",
            "publishedAt",
        ]

    for field in possible_fields:
        if field in item:
            dt = parse_datetime(item.get(field))

            if dt:
                return dt

    return None


def is_in_window(dt):
    if not dt:
        return False

    return START_TIME <= dt < END_TIME


# ============================================================
# APIFY
# ============================================================

def run_actor(actor_id, run_input):
    """
    Starts an Apify actor and waits for completion.
    """

    encoded_actor = quote(
        actor_id,
        safe=""
    )

    url = (
        f"https://api.apify.com/v2/acts/"
        f"{encoded_actor}/runs"
    )

    headers = {
        "Authorization": f"Bearer {APIFY_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        json=run_input,
        timeout=60,
    )

    response.raise_for_status()

    run_data = response.json()["data"]

    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    # Wait for the actor
    status_url = (
        f"https://api.apify.com/v2/actor-runs/"
        f"{run_id}"
    )

    for _ in range(180):
        status_response = requests.get(
            status_url,
            headers=headers,
            timeout=60,
        )

        status_response.raise_for_status()

        status = status_response.json()["data"]["status"]

        if status in {
            "SUCCEEDED",
            "FAILED",
            "ABORTED",
            "TIMED-OUT",
        }:
            break

        time.sleep(2)

    if status != "SUCCEEDED":
        raise RuntimeError(
            f"Apify actor failed with status: {status}"
        )

    dataset_url = (
        f"https://api.apify.com/v2/datasets/"
        f"{dataset_id}/items"
        f"?clean=true&format=json"
    )

    dataset_response = requests.get(
        dataset_url,
        headers=headers,
        timeout=120,
    )

    dataset_response.raise_for_status()

    return dataset_response.json()


# ============================================================
# SCRAPE TIKTOK
# ============================================================

def scrape_tiktok(username):
    actor_id = "clockworks~tiktok-scraper"

    run_input = {
        "profiles": [username],
        "resultsPerPage": 100,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
    }

    try:
        return run_actor(
            actor_id,
            run_input
        )

    except Exception as e:
        print(
            f"TikTok error @{username}: {e}"
        )
        return []


# ============================================================
# SCRAPE INSTAGRAM
# ============================================================

def scrape_instagram(username):
    actor_id = "apify~instagram-scraper"

    run_input = {
        "directUrls": [
            f"https://www.instagram.com/{username}/"
        ],
        "resultsType": "posts",
        "resultsLimit": 100,
        "searchType": "user",
    }

    try:
        return run_actor(
            actor_id,
            run_input
        )

    except Exception as e:
        print(
            f"Instagram error @{username}: {e}"
        )
        return []


# ============================================================
# CHECK ACCOUNT
# ============================================================

def check_account(account):
    platform = account["platform"]
    username = account["username"]

    print(
        f"Checking {platform} @{username}..."
    )

    if platform == "tiktok":
        items = scrape_tiktok(username)
    else:
        items = scrape_instagram(username)

    matching = []

    for item in items:
        dt = get_timestamp(
            item,
            platform
        )

        if is_in_window(dt):
            matching.append({
                "timestamp": dt.isoformat(),
                "url": (
                    item.get("webVideoUrl")
                    or item.get("url")
                    or item.get("postUrl")
                    or item.get("permalink")
                ),
            })

    matching.sort(
        key=lambda x: x["timestamp"]
    )

    count = len(matching)

    if count >= REQUIRED_UPLOADS:
        status = "✅"
    elif count > 0:
        status = "⚠️"
    else:
        status = "❌"

    return {
        "owner": account["owner"],
        "platform": platform,
        "username": username,
        "count": count,
        "required": REQUIRED_UPLOADS,
        "status": status,
        "uploads": matching,
    }


# ============================================================
# RUN ALL ACCOUNTS
# ============================================================

def main():

    print()
    print("====================================")
    print("       RENAE UPLOAD CHECK")
    print("====================================")
    print()
    print(f"Date: {TARGET_DATE}")
    print(f"Required: {REQUIRED_UPLOADS} uploads")
    print(f"Window: {WINDOW_HOURS} hours")
    print()

    results = []

    for account in ACCOUNTS:
        result = check_account(account)

        results.append(result)

        print(
            f"{result['status']} "
            f"{result['platform'].title()} "
            f"@{result['username']} "
            f"{result['count']}/{REQUIRED_UPLOADS}"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    total_accounts = len(results)

    completed = sum(
        1
        for r in results
        if r["count"] >= REQUIRED_UPLOADS
    )

    behind = total_accounts - completed

    # ========================================================
    # CLEAN MARKDOWN
    # ========================================================

    lines = []

    lines.append("# 🎬 Renae Upload Check")
    lines.append("")
    lines.append(
        f"**📅 Date:** {TARGET_DATE}"
    )
    lines.append(
        f"**🎯 Required:** {REQUIRED_UPLOADS} uploads/account"
    )
    lines.append(
        f"**⏱️ Window:** {WINDOW_HOURS} hours"
    )
    lines.append("")

    lines.append(
        f"## 📊 {completed}/{total_accounts} Accounts Complete"
    )

    if behind == 0:
        lines.append("")
        lines.append(
            "🎉 **Everyone has completed their uploads!**"
        )
    else:
        lines.append("")
        lines.append(
            f"⚠️ **{behind} account(s) need more uploads.**"
        )

    lines.append("")

    # Group by owner
    owners = []

    for result in results:
        if result["owner"] not in owners:
            owners.append(result["owner"])

    for owner in owners:

        lines.append(
            f"## 👤 {owner}"
        )
        lines.append("")

        owner_results = [
            r for r in results
            if r["owner"] == owner
        ]

        for platform in ["tiktok", "instagram"]:

            platform_results = [
                r
                for r in owner_results
                if r["platform"] == platform
            ]

            if not platform_results:
                continue

            lines.append(
                f"### {platform.title()}"
            )
            lines.append("")

            for r in platform_results:

                lines.append(
                    f"- {r['status']} "
                    f"**@{r['username']}** — "
                    f"**{r['count']}/{REQUIRED_UPLOADS}**"
                )

            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated automatically by Renae Upload Tracker._"
    )

    clean_markdown = "\n".join(lines)

    # ========================================================
    # SAVE CLEAN RESULT
    # ========================================================

    results_dir = Path("results")
    results_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    markdown_file = (
        results_dir /
        f"{TARGET_DATE}.md"
    )

    json_file = (
        results_dir /
        f"{TARGET_DATE}.json"
    )

    markdown_file.write_text(
        clean_markdown,
        encoding="utf-8"
    )

    # JSON is kept only for the program.
    # It is still much cleaner than raw Apify output.
    clean_json = {
        "date": str(TARGET_DATE),
        "required_uploads": REQUIRED_UPLOADS,
        "window_hours": WINDOW_HOURS,
        "total_accounts": total_accounts,
        "completed_accounts": completed,
        "accounts_needing_uploads": behind,
        "results": results,
    }

    json_file.write_text(
        json.dumps(
            clean_json,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # ========================================================
    # ALSO PRINT CLEAN RESULT TO ACTIONS
    # ========================================================

    print()
    print("====================================")
    print("         CLEAN RESULT")
    print("====================================")
    print()

    print(
        f"📅 {TARGET_DATE}"
    )
    print(
        f"📊 {completed}/{total_accounts} complete"
    )
    print()

    for owner in owners:

        print(
            f"👤 {owner}"
        )

        owner_results = [
            r for r in results
            if r["owner"] == owner
        ]

        for r in owner_results:
            print(
                f"  {r['status']} "
                f"{r['platform'].title()} "
                f"@{r['username']} "
                f"{r['count']}/{REQUIRED_UPLOADS}"
            )

        print()

    print(
        f"⚠️ Accounts needing uploads: {behind}"
    )

    print()
    print(
        f"Clean result saved to: {markdown_file}"
    )
    print(
        f"Machine result saved to: {json_file}"
    )


if __name__ == "__main__":
    main()
