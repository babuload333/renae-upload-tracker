import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests


APIFY_API_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

TIKTOK_ACTOR = "clockworks~tiktok-scraper"
INSTAGRAM_ACTOR = "apify~instagram-reel-scraper"

REQUIRED_UPLOADS = 3
WINDOW_HOURS = 24

IST = ZoneInfo("Asia/Kolkata")


def apify_run(actor, token, actor_input):
    """Run an Apify Actor and return its dataset items."""

    url = APIFY_API_URL.format(actor=actor)

    response = requests.post(
        url,
        params={"token": token},
        json=actor_input,
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"Unexpected Apify response from {actor}: "
            f"{type(data).__name__}"
        )

    return data


def parse_timestamp(value):
    """Convert common timestamp formats to UTC datetime."""

    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            number = float(value)

            if number > 10**11:
                number /= 1000

            return datetime.fromtimestamp(
                number,
                timezone.utc,
            )

        text = str(value).strip()

        if not text:
            return None

        if text.isdigit():
            number = float(text)

            if number > 10**11:
                number /= 1000

            return datetime.fromtimestamp(
                number,
                timezone.utc,
            )

        text = text.replace("Z", "+00:00")

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def get_tiktok_timestamp(item):
    """Get TikTok upload timestamp."""

    for key in [
        "createTimeISO",
        "createTime",
        "create_time",
    ]:
        if key in item:
            timestamp = parse_timestamp(item[key])

            if timestamp:
                return timestamp

    return None


def get_tiktok_username(item):
    """Get TikTok author username."""

    author = item.get("authorMeta")

    if isinstance(author, dict):
        for key in [
            "name",
            "uniqueId",
            "unique_id",
            "username",
        ]:
            if author.get(key):
                return str(author[key]).lstrip("@").lower()

    for key in [
        "authorUsername",
        "username",
        "uniqueId",
    ]:
        if item.get(key):
            return str(item[key]).lstrip("@").lower()

    return None


def get_instagram_timestamp(item):
    """Get Instagram Reel timestamp."""

    for key in [
        "timestamp",
        "publishedAt",
        "takenAt",
        "taken_at",
        "date",
        "createdAt",
        "created_at",
    ]:
        if key in item:
            timestamp = parse_timestamp(item[key])

            if timestamp:
                return timestamp

    return None


def get_instagram_username(item):
    """Get Instagram Reel owner username."""

    owner = item.get("ownerUsername")

    if owner:
        return str(owner).lstrip("@").lower()

    owner = item.get("owner")

    if isinstance(owner, dict):
        for key in [
            "username",
            "userName",
            "name",
        ]:
            if owner.get(key):
                return str(owner[key]).lstrip("@").lower()

    for key in [
        "username",
        "userName",
        "authorUsername",
    ]:
        if item.get(key):
            return str(item[key]).lstrip("@").lower()

    return None


def get_video_url(item, platform):
    """Get the public video URL when available."""

    if platform == "tiktok":
        for key in [
            "webVideoUrl",
            "webVideoUrlNoWaterMark",
            "url",
        ]:
            if item.get(key):
                return item[key]

    else:
        for key in [
            "url",
            "inputUrl",
            "shortCode",
        ]:
            if item.get(key):
                value = item[key]

                if key == "shortCode":
                    return (
                        "https://www.instagram.com/reel/"
                        + str(value)
                        + "/"
                    )

                return value

    return None


def build_window(target_date):
    """
    Daily mode:
        previous rolling 24 hours.

    Historical mode:
        the requested date in India/Kerala time.
    """

    now_utc = datetime.now(timezone.utc)

    if target_date:

        local_start = datetime.strptime(
            target_date,
            "%Y-%m-%d",
        ).replace(
            tzinfo=IST
        )

        local_end = local_start + timedelta(days=1)

        return (
            local_start.astimezone(timezone.utc),
            local_end.astimezone(timezone.utc),
        )

    return (
        now_utc - timedelta(hours=WINDOW_HOURS),
        now_utc,
    )


def check_tiktok(accounts, token, start, end):
    """Check all TikTok accounts through Apify."""

    usernames = [
        account["username"]
        for account in accounts
    ]

    actor_input = {
        "profiles": usernames,

        "hashtags": [],

        "resultsPerPage": 10,

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

    items = apify_run(
        TIKTOK_ACTOR,
        token,
        actor_input,
    )

    results = {}

    for account in accounts:

        username = account["username"].lower()

        results[username] = []

    for item in items:

        username = get_tiktok_username(item)
        timestamp = get_tiktok_timestamp(item)

        if not username or not timestamp:
            continue

        if username not in results:
            continue

        if start <= timestamp < end:

            results[username].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "url": get_video_url(
                        item,
                        "tiktok",
                    ),
                }
            )

    return results


def check_instagram(accounts, token, start, end):
    """Check all Instagram Reel accounts through Apify."""

    usernames = [
        account["url"]
        for account in accounts
    ]

    actor_input = {
        "username": usernames,

        "resultsLimit": 20,

        "onlyPostsNewerThan": start.isoformat(),

        "skipPinnedPosts": True,

        "skipTrialReels": False,

        "includeSharesCount": False,

        "includeTranscript": False,

        "includeDownloadedVideo": False,
    }

    items = apify_run(
        INSTAGRAM_ACTOR,
        token,
        actor_input,
    )

    results = {}

    for account in accounts:

        results[
            account["username"].lower()
        ] = []

    for item in items:

        username = get_instagram_username(item)
        timestamp = get_instagram_timestamp(item)

        if not username or not timestamp:
            continue

        if username not in results:
            continue

        if start <= timestamp < end:

            results[username].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "url": get_video_url(
                        item,
                        "instagram",
                    ),
                }
            )

    return results


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        help="Historical date, e.g. 2026-08-21",
    )

    args = parser.parse_args()

    token = os.environ.get(
        "APIFY_API_TOKEN"
    )

    if not token:

        raise RuntimeError(
            "APIFY_API_TOKEN GitHub secret is missing."
        )

    with open(
        "accounts.json",
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(file)

    accounts = config["accounts"]

    start, end = build_window(
        args.date
    )

    tiktok_accounts = [
        account
        for account in accounts
        if account["platform"] == "tiktok"
    ]

    instagram_accounts = [
        account
        for account in accounts
        if account["platform"] == "instagram"
    ]

    print()
    print("=" * 90)
    print("RENAE UPLOAD TRACKER")
    print("=" * 90)
    print(
        "Window:",
        start.isoformat(),
        "→",
        end.isoformat(),
    )
    print("=" * 90)

    tiktok_results = check_tiktok(
        tiktok_accounts,
        token,
        start,
        end,
    )

    instagram_results = check_instagram(
        instagram_accounts,
        token,
        start,
        end,
    )

    final_results = []

    for account in accounts:

        username = account[
            "username"
        ].lower()

        if account["platform"] == "tiktok":

            uploads = tiktok_results.get(
                username,
                [],
            )

        else:

            uploads = instagram_results.get(
                username,
                [],
            )

        uploads.sort(
            key=lambda x: x["timestamp"],
            reverse=True,
        )

        count = len(uploads)

        if count >= REQUIRED_UPLOADS:
            status = "PASS"

        else:
            status = "BEHIND"

        result = {
            **account,

            "status": status,

            "count": count,

            "required": REQUIRED_UPLOADS,

            "times": [
                upload["timestamp"]
                for upload in uploads
            ],

            "urls": [
                upload["url"]
                for upload in uploads
                if upload["url"]
            ],
        }

        final_results.append(result)

        print(
            f'{account["owner"]:8} '
            f'{account["platform"]:9} '
            f'@{account["username"]:25} '
            f'{count}/{REQUIRED_UPLOADS} '
            f'{status}'
        )

    os.makedirs(
        "results",
        exist_ok=True,
    )

    if args.date:

        filename = (
            f"{args.date}.json"
        )

    else:

        filename = (
            datetime.now(timezone.utc)
            .strftime(
                "%Y-%m-%dT%H-%M-%SZ.json"
            )
        )

    output = {

        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "timezone": "Asia/Kolkata",

        "window_start": start.isoformat(),

        "window_end": end.isoformat(),

        "target_date": args.date,

        "required_uploads": REQUIRED_UPLOADS,

        "window_hours": WINDOW_HOURS,

        "results": final_results,
    }

    output_path = os.path.join(
        "results",
        filename,
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
    print(
        f"Results saved to: {output_path}"
    )
    print()


if __name__ == "__main__":
    main()
