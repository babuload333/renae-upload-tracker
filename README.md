# Renae Upload Tracker v2

Free GitHub Actions tracker for the 10 public Renae Erica Instagram/TikTok accounts.

## What changed in v2

The old HTML timestamp parser was too primitive and returned misleading zeroes.

This version uses:
- **TikTok:** `tt` (`tamnd/tiktok-cli`), an open-source CLI that reads public TikTok data without an API key or login.
- **Instagram:** `Instaloader` 4.15.3, using its profile post/reel iterators.

The tracker counts **video uploads** in a rolling 24-hour window. If a platform blocks access or timestamps cannot be verified, it reports `UNVERIFIED`.

## Manual historical check

In GitHub Actions:
1. Open **Daily Renae Upload Check**
2. Tap **Run workflow**
3. Enter `2026-08-21` in **target_date**
4. Run it

The result will be saved as `results/2026-08-21.json`.

## Important

This is still dependent on the public surfaces of Instagram and TikTok. GitHub-hosted runners can be blocked by social platforms. The tracker intentionally does not turn a blocked request into `0`.

## Accounts

All 10 accounts are in `accounts.json`.

## Sources

TikTok collector: https://github.com/tamnd/tiktok-cli
Instagram collector: https://github.com/instaloader/instaloader
