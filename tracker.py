import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests


# ============================================================
# CONFIG
# ============================================================

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")

TIKTOK_ACTOR = "clockworks~tiktok-scraper"
INSTAGRAM_ACTOR = "apify~instagram-api-scraper"

REQUIRED_UPLOADS = 3
WINDOW_HOURS = 24

IST = ZoneInfo("Asia/Kolkata")

TIKTOK_ACCOUNTS = [
    "renaeericacentral",
    "renaeericavods",
    "renaeericatv",
    "renaeericadaily",
    "renaeerica.fanpage",
]

INSTAGRAM_ACCOUNTS = [
    "renaeericacentral",
    "renaeericahub",
    "renaeericatvx",
    "renaeericadaily",
    "renaeerica.fanpage",
]


# ============================================================
# APIFY
# ============================================================

def run_apify(actor, actor_input):
    if not APIFY_TOKEN:
        raise RuntimeError(
            "APIFY_API_TOKEN GitHub secret is missing."
        )

    url = (
        f"https://api.apify.com/v2/acts/"
        f"{actor}/run-sync-get-dataset-items"
    )

    response = requests.post(
        url,
        params={"token": APIFY_TOKEN},
        json=actor_input,
        timeout=300,
    )

    if not response.ok:
        raise RuntimeError(
            f"Apify returned HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"Unexpected Apify response: "
            f"{type(data).__name__}"
        )

    return data


# ============================================================
# TIME
# ============================================================

def parse_timestamp(value):
    if value is None:
        return None

    try:
        # Unix timestamp
        if isinstance(value, (int, float)):
            value = float(value)

            if value > 10_000_000_000:
                value /= 1000

            return datetime.fromtimestamp(
                value,
                tz=timezone.utc,
            )

        value = str(value).strip()

        if not value:
            return None

        # Numeric timestamp stored as string
        if value.isdigit():
            number = float(value)

            if number > 10_000_000_000:
                number /= 1000

            return datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )

        # ISO timestamp
        value = value.replace(
            "Z",
            "+00:00",
        )

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def build_window(target_date):
    """
    Historical:
        00:00 to 00:00 of the requested date
        in India time.

    Normal:
        Previous rolling 24 hours.
    """

    now = datetime.now(timezone.utc)

    if target_date:
        target_date = str(
            target_date
        ).strip()

        # Remove accidental quotes
        target_date = (
            target_date
            .strip('"')
            .strip("'")
            .strip()
        )

        try:
            # IMPORTANT:
            # Explicitly parse YYYY-MM-DD.
            local_start = datetime.strptime(
                target_date,
                "%Y-%m-%d",
            ).replace(
                tzinfo=IST
            )

        except ValueError:
            raise ValueError(
                f"Invalid target_date "
                f"{target_date!r}. "
                f"Use YYYY-MM-DD, "
                f"for example 2026-08-21."
            )

        local_end = (
            local_start
            + timedelta(days=1)
        )

        return (
            local_start.astimezone(
                timezone.utc
            ),
            local_end.astimezone(
                timezone.utc
            ),
        )

    return (
        now - timedelta(
            hours=WINDOW_HOURS
        ),
        now,
    )


# ============================================================
# TIKTOK
# ============================================================

def get_tiktok_username(item):

    author = item.get("authorMeta")

    if isinstance(author, dict):

        for key in [
            "name",
            "uniqueId",
            "unique_id",
            "username",
        ]:

            value = author.get(key)

            if value:
                return (
                    str(value)
                    .lstrip("@")
                    .lower()
                )

    for key in [
        "authorUsername",
        "username",
        "uniqueId",
    ]:

        value = item.get(key)

        if value:
            return (
                str(value)
                .lstrip("@")
                .lower()
            )

    return None


def get_tiktok_time(item):

    for key in [
        "createTimeISO",
        "createTime",
        "create_time",
    ]:

        timestamp = parse_timestamp(
            item.get(key)
        )

        if timestamp:
            return timestamp

    return None


def get_tiktok_url(item):

    for key in [
        "webVideoUrl",
        "webVideoUrlNoWaterMark",
        "url",
    ]:

        if item.get(key):
            return item[key]

    return None


def check_tiktok(start, end):

    actor_input = {
        "profiles": TIKTOK_ACCOUNTS,

        "resultsPerPage": 20,

        "profileScrapeSections": [
            "videos"
        ],

        "profileSorting": "latest",

        "excludePinnedPosts": True,

        "searchQueries": [],

        "postURLs": [],

        "scrapeRelatedVideos": False,

        "scrapeAdditionalAuthorMeta": False,

        "shouldDownloadVideos": False,

        "shouldDownloadCovers": False,

        "shouldDownloadSlideshowImages": False,

        "shouldDownloadAvatars": False,

        "shouldDownloadMusicCovers": False,

        "commentsPerPost": 0,

        "topLevelCommentsPerPost": 0,

        "maxRepliesPerComment": 0,
    }

    print("Running TikTok Actor...")

    items = run_apify(
        TIKTOK_ACTOR,
        actor_input,
    )

    results = {
        username: []
        for username in TIKTOK_ACCOUNTS
    }

    for item in items:

        username = get_tiktok_username(
            item
        )

        timestamp = get_tiktok_time(
            item
        )

        if not username:
            continue

        if not timestamp:
            continue

        if username not in results:
            continue

        if start <= timestamp < end:

            results[username].append(
                {
                    "timestamp":
                        timestamp.isoformat(),

                    "url":
                        get_tiktok_url(item),
                }
            )

    return results


# ============================================================
# INSTAGRAM REELS
# ============================================================

def get_instagram_username(item):

    for key in [
        "ownerUsername",
        "username",
        "authorUsername",
    ]:

        value = item.get(key)

        if value:
            return (
                str(value)
                .lstrip("@")
                .lower()
            )

    owner = item.get("owner")

    if isinstance(owner, dict):

        for key in [
            "username",
            "userName",
        ]:

            value = owner.get(key)

            if value:
                return (
                    str(value)
                    .lstrip("@")
                    .lower()
                )

    return None


def get_instagram_time(item):

    for key in [
        "timestamp",
        "publishedAt",
        "takenAt",
        "createdAt",
        "created_at",
        "date",
    ]:

        timestamp = parse_timestamp(
            item.get(key)
        )

        if timestamp:
            return timestamp

    return None


def get_instagram_url(item):

    if item.get("url"):
        return item["url"]

    if item.get("inputUrl"):
        return item["inputUrl"]

    shortcode = item.get(
        "shortCode"
    )

    if shortcode:

        return (
            "https://www.instagram.com/reel/"
            f"{shortcode}/"
        )

    return None


def check_instagram(start, end):

    urls = [
        f"https://www.instagram.com/{username}/"
        for username in INSTAGRAM_ACCOUNTS
    ]

    actor_input = {

        "directUrls": urls,

        "resultsType": "reels",

        "resultsLimit": 20,

        # Don't use an exact timestamp here.
        # We fetch the latest 20 and filter locally.
        "addParentData": True,
    }

    print("Running Instagram Reel Actor...")

    items = run_apify(
        INSTAGRAM_ACTOR,
        actor_input,
    )

    results = {
        username: []
        for username in INSTAGRAM_ACCOUNTS
    }

    for item in items:

        # Ignore diagnostic/error rows
        if item.get("errorReason"):
            continue

        username = (
            get_instagram_username(item)
        )

        timestamp = (
            get_instagram_time(item)
        )

        if not username:
            continue

        if not timestamp:
            continue

        if username not in results:
            continue

        if start <= timestamp < end:

            results[username].append(
                {
                    "timestamp":
                        timestamp.isoformat(),

                    "url":
                        get_instagram_url(item),
                }
            )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=False,
        default=None,
        help=(
            "Historical date in "
            "YYYY-MM-DD format."
        ),
    )

    args = parser.parse_args()

    start, end = build_window(
        args.date
    )

    print()
    print("=" * 80)
    print("RENAE UPLOAD TRACKER")
    print("=" * 80)

    print(
        "Start UTC:",
        start.isoformat()
    )

    print(
        "End UTC:",
        end.isoformat()
    )

    print(
        "Required uploads:",
        REQUIRED_UPLOADS
    )

    print("=" * 80)
    print()

    # --------------------------------------------------------
    # Run both platforms
    # --------------------------------------------------------

    tiktok_results = check_tiktok(
        start,
        end,
    )

    instagram_results = check_instagram(
        start,
        end,
    )

    # --------------------------------------------------------
    # Account information
    # --------------------------------------------------------

    accounts = [

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

        {
            "owner": "Prudhiv",
            "platform": "tiktok",
            "username": "renaeericatv",
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

        {
            "owner": "Prudhiv",
            "platform": "tiktok",
            "username": "renaeericadaily",
        },

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

    final_results = []

    # --------------------------------------------------------
    # Calculate results
    # --------------------------------------------------------

    for account in accounts:

        username = account[
            "username"
        ].lower()

        platform = account[
            "platform"
        ]

        if platform == "tiktok":

            uploads = tiktok_results.get(
                username,
                []
            )

        else:

            uploads = instagram_results.get(
                username,
                []
            )

        uploads.sort(
            key=lambda item:
                item["timestamp"],
            reverse=True,
        )

        count = len(uploads)

        if count >= REQUIRED_UPLOADS:
            status = "PASS"
        else:
            status = "BEHIND"

        result = {
            "owner":
                account["owner"],

            "platform":
                platform,

            "username":
                username,

            "status":
                status,

            "count":
                count,

            "required":
                REQUIRED_UPLOADS,

            "times":
                [
                    upload["timestamp"]
                    for upload in uploads
                ],

            "urls":
                [
                    upload["url"]
                    for upload in uploads
                    if upload.get("url")
                ],
        }

        final_results.append(
            result
        )

        print(
            f'{account["owner"]:8} | '
            f'{platform:9} | '
            f'@{username:25} | '
            f'{count}/{REQUIRED_UPLOADS} | '
            f'{status}'
        )

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    os.makedirs(
        "results",
        exist_ok=True
    )

    if args.date:

        filename = (
            f"{args.date}.json"
        )

    else:

        filename = (
            datetime.now(
                timezone.utc
            ).strftime(
                "%Y-%m-%dT%H-%M-%SZ.json"
            )
        )

    output = {

        "checked_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "timezone":
            "Asia/Kolkata",

        "target_date":
            args.date,

        "window_start":
            start.isoformat(),

        "window_end":
            end.isoformat(),

        "required_uploads":
            REQUIRED_UPLOADS,

        "window_hours":
            WINDOW_HOURS,

        "results":
            final_results,
    }

    output_path = os.path.join(
        "results",
        filename
    )

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

    print()
    print("=" * 80)
    print(
        f"Saved: {output_path}"
    )
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
