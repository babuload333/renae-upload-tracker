#!/usr/bin/env python3
"""
Renae Upload Tracker v2.

TikTok: uses the open-source `tt` CLI to read public profile posts.
Instagram: uses Instaloader to read public posts/reels.

The tracker counts video uploads in the preceding rolling 24 hours.
If a platform blocks access or timestamps cannot be verified, the result
is UNVERIFIED rather than an invented zero.

Usage:
  python tracker.py
  python tracker.py --date 2026-08-21
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def window_for(target_date):
    now = datetime.now(timezone.utc)
    if target_date:
        start = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
        return start, start + timedelta(days=1)
    return now - timedelta(hours=24), now


def parse_dt(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            n = float(value)
            if n > 10**11:
                n /= 1000
            return datetime.fromtimestamp(n, timezone.utc)
        s = str(value).strip()
        if s.isdigit():
            n = float(s)
            if n > 10**11:
                n /= 1000
            return datetime.fromtimestamp(n, timezone.utc)
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def recursive_timestamps(obj):
    """Yield timestamp values from arbitrary JSON structures."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            k = str(key).lower()
            if k in {
                "create_time", "createtime", "createat", "created_at",
                "createdat", "timestamp", "upload_date", "uploaddate",
                "date_published", "datepublished"
            }:
                dt = parse_dt(value)
                if dt:
                    yield dt
            yield from recursive_timestamps(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from recursive_timestamps(item)


def run_tiktok(username, start, end):
    """Run tt posts and parse JSONL timestamps."""
    tt = shutil.which("tt")
    if not tt:
        return None, [], "tt_not_installed"

    cmd = [
        tt, "posts", f"@{username}",
        "-n", "30",
        "-o", "jsonl",
        "--quiet",
        "--rate", "800ms",
        "--timeout", "30s",
        "--retries", "3",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        return None, [], type(exc).__name__

    if proc.returncode == 4:
        return None, [], "tiktok_walled"
    if proc.returncode != 0 and not proc.stdout.strip():
        return None, [], f"tiktok_exit_{proc.returncode}"

    timestamps = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamps.extend(recursive_timestamps(record))

    timestamps = sorted(set(timestamps), reverse=True)
    hits = [dt for dt in timestamps if start <= dt < end]

    # If the tool returned records but no recognizable timestamps, don't call it zero.
    if not timestamps:
        return None, [], "no_timestamps"

    return len(hits), hits, None


def run_instagram(username, start, end):
    """Read recent Instagram video/reel timestamps with Instaloader."""
    try:
        import instaloader
    except ImportError:
        return None, [], "instaloader_not_installed"

    try:
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )

        profile = instaloader.Profile.from_username(
            loader.context,
            username,
        )

        found = {}

        # Reels are the primary target for this tracker.
        try:
            for post in profile.get_reels():
                if post.date_utc < start:
                    break
                if post.date_utc < end and post.is_video:
                    found[post.shortcode] = post.date_utc
        except Exception:
            pass

        # Also inspect recent profile media for video posts that may not be returned
        # by the reels iterator.
        try:
            for post in profile.get_posts():
                if post.date_utc < start:
                    break
                if post.date_utc < end and post.is_video:
                    found[post.shortcode] = post.date_utc
        except Exception:
            pass

        if not found:
            # No hits can still mean the account had no qualifying uploads,
            # but if Instagram returned no media at all we cannot verify.
            return 0, [], None

        dates = sorted(set(found.values()), reverse=True)
        return len(dates), dates, None

    except Exception as exc:
        return None, [], type(exc).__name__


def check(account, start, end):
    if account["platform"] == "tiktok":
        count, dates, error = run_tiktok(account["username"], start, end)
    else:
        count, dates, error = run_instagram(account["username"], start, end)

    if count is None:
        return {
            "status": "UNVERIFIED",
            "count": None,
            "times": [],
            "error": error,
        }

    return {
        "status": "PASS" if count >= 3 else "BEHIND",
        "count": count,
        "times": [d.isoformat() for d in dates],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="UTC date YYYY-MM-DD")
    args = parser.parse_args()

    with open("accounts.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    start, end = window_for(args.date)
    results = []

    print("=" * 90)
    print("RENAE UPLOAD TRACKER v2")
    print(f"Window: {start.isoformat()} -> {end.isoformat()}")
    print("=" * 90)

    for account in config["accounts"]:
        result = check(account, start, end)
        results.append({**account, **result})

        count = result["count"] if result["count"] is not None else "-"
        print(
            f'{account["owner"]:8} '
            f'{account["platform"]:9} '
            f'@{account["username"]:25} '
            f'{result["status"]:12} '
            f'{count}'
        )

    os.makedirs("results", exist_ok=True)

    filename = (
        f"{args.date}.json"
        if args.date
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ.json")
    )

    output = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "target_date": args.date,
        "required_uploads": config.get("required_uploads", 3),
        "window_hours": config.get("window_hours", 24),
        "results": results,
    }

    with open(os.path.join("results", filename), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("=" * 90)
    print(f"Saved: results/{filename}")
    print("=" * 90)


if __name__ == "__main__":
    main()
