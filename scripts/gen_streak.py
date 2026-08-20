#!/usr/bin/env python3
"""Generate an accurate GitHub streak SVG straight from the GraphQL API.

Replaces the flaky demolab.com badge. Computes total contributions,
current streak and longest streak from the real contribution calendar,
then renders an SVG that matches the profile's dark/pink theme.

Requires: GH_TOKEN (or GITHUB_TOKEN) in the environment.
Usage: python gen_streak.py <username> <output.svg>
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

USER = sys.argv[1] if len(sys.argv) > 1 else "SrinivasSelvaraj"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "assets/streak.svg"

# Theme (matches the previous demolab params)
BG          = "#05070D"
RING        = "#F472B6"
FIRE        = "#F472B6"
CUR_LABEL   = "#22D3EE"
SIDE_LABELS = "#A78BFA"
DATES       = "#8FA3C8"
CUR_NUM     = "#FFFFFF"
SIDE_NUMS   = "#E8ECF4"
DIVIDER     = "#1B2330"


def gh_graphql(query):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh graphql failed: {result.stderr}")
    return json.loads(result.stdout)


def fetch_all_days(user):
    created = gh_graphql(f'{{ user(login: "{user}") {{ createdAt }} }}')
    created_at = created["data"]["user"]["createdAt"][:10]
    start_year = int(created_at[:4])
    now = datetime.now(timezone.utc)
    days = {}
    total = 0
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to  = f"{year}-12-31T23:59:59Z"
        if year == start_year:
            frm = created["data"]["user"]["createdAt"]
        if year == now.year:
            to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        q = f'''{{
          user(login: "{user}") {{
            contributionsCollection(from: "{frm}", to: "{to}") {{
              contributionCalendar {{
                totalContributions
                weeks {{ contributionDays {{ date contributionCount }} }}
              }}
            }}
          }}
        }}'''
        data = gh_graphql(q)
        cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        total += cal["totalContributions"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return created_at, total, days


def compute_streaks(days):
    if not days:
        return (0, None, None), (0, None, None)
    sorted_dates = sorted(days.keys())
    d0 = date.fromisoformat(sorted_dates[0])
    d1 = date.fromisoformat(sorted_dates[-1])

    # Longest streak
    longest = 0
    longest_start = longest_end = None
    run = 0
    run_start = None
    cur = d0
    while cur <= d1:
        s = cur.isoformat()
        if days.get(s, 0) > 0:
            if run == 0:
                run_start = cur
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
                longest_end = cur
        else:
            run = 0
        cur += timedelta(days=1)

    # Current streak (today may be 0 since the day is not over)
    today = d1
    cur_len = 0
    cur_start = None
    cur_end = None
    dd = today
    if days.get(today.isoformat(), 0) == 0:
        dd = today - timedelta(days=1)
    while dd >= d0:
        s = dd.isoformat()
        if days.get(s, 0) > 0:
            cur_len += 1
            cur_start = dd
            if cur_end is None:
                cur_end = dd
            dd -= timedelta(days=1)
        else:
            break

    return (longest, longest_start, longest_end), (cur_len, cur_start, cur_end)


def fmt(d):
    return d.strftime("%b %-d") if d else ""


def fmt_range(a, b):
    if not a:
        return ""
    if a == b:
        return fmt(a)
    ya, yb = a.year, b.year
    if ya != yb:
        return f"{a.strftime('%b %-d, %Y')} - {b.strftime('%b %-d, %Y')}"
    return f"{fmt(a)} - {fmt(b)}"


def build_svg(created_at, total, longest, current):
    lg, lg_s, lg_e = longest
    cu, cu_s, cu_e = current
    created_d = date.fromisoformat(created_at)
    total_range = f"{created_d.strftime('%b %-d, %Y')} - Present"

    W, H = 980, 200
    col = W / 3
    cx = col + col / 2  # centre column x for the ring

    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <style>
    .num {{ font: 800 38px 'Segoe UI', Ubuntu, sans-serif; }}
    .lbl {{ font: 700 15px 'Segoe UI', Ubuntu, sans-serif; }}
    .dt  {{ font: 400 13px 'Segoe UI', Ubuntu, sans-serif; fill: {DATES}; }}
  </style>
  <rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
  <line x1="{col}" y1="45" x2="{col}" y2="{H-45}" stroke="{DIVIDER}" stroke-width="1"/>
  <line x1="{2*col}" y1="45" x2="{2*col}" y2="{H-45}" stroke="{DIVIDER}" stroke-width="1"/>

  <!-- Total contributions -->
  <text x="{col/2}" y="80" text-anchor="middle" class="num" fill="{SIDE_NUMS}">{total}</text>
  <text x="{col/2}" y="118" text-anchor="middle" class="lbl" fill="{SIDE_LABELS}">Total Contributions</text>
  <text x="{col/2}" y="148" text-anchor="middle" class="dt">{total_range}</text>

  <!-- Current streak (centre, ringed) -->
  <circle cx="{cx}" cy="82" r="42" fill="none" stroke="{RING}" stroke-width="5"/>
  <path d="M {cx} 30 q -9 12 0 22 q 9 -4 0 -22 z" fill="{FIRE}"/>
  <text x="{cx}" y="95" text-anchor="middle" class="num" fill="{CUR_NUM}">{cu}</text>
  <text x="{cx}" y="152" text-anchor="middle" class="lbl" fill="{CUR_LABEL}">Current Streak</text>
  <text x="{cx}" y="178" text-anchor="middle" class="dt">{fmt_range(cu_s, cu_e)}</text>

  <!-- Longest streak -->
  <text x="{2.5*col}" y="80" text-anchor="middle" class="num" fill="{SIDE_NUMS}">{lg}</text>
  <text x="{2.5*col}" y="118" text-anchor="middle" class="lbl" fill="{SIDE_LABELS}">Longest Streak</text>
  <text x="{2.5*col}" y="148" text-anchor="middle" class="dt">{fmt_range(lg_s, lg_e)}</text>
</svg>
'''
    return svg


def main():
    created_at, total, days = fetch_all_days(USER)
    longest, current = compute_streaks(days)
    print(f"Total: {total} | Current: {current[0]} ({fmt_range(current[1], current[2])}) | "
          f"Longest: {longest[0]} ({fmt_range(longest[1], longest[2])})", file=sys.stderr)
    svg = build_svg(created_at, total, longest, current)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
