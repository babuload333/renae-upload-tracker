# Renae Upload Tracker

Tracks the 10 public Renae Erica Instagram/TikTok accounts and checks whether each has at least **3 videos/reels in the preceding 24 hours**.

## Accounts
See `accounts.json`.

## Run locally
```bash
python tracker.py
python tracker.py --date 2026-08-21
```

The historical command is best-effort. Public social platforms can hide timestamps or block automated requests. The tracker therefore reports `UNVERIFIED` rather than inventing a zero.

## GitHub Actions
The workflow runs daily and can also be started manually from the **Actions** tab. GitHub supports scheduled workflows using `on.schedule` and cron syntax. citeturn0search0

## Important
This is a free/open-source approach. It does not bypass logins, private accounts, or platform access controls. It only uses publicly exposed profile-page data.
