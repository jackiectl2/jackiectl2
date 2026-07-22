#!/usr/bin/env python3
"""Render the contribution-streak card into assets/streak-{dark,light}.svg.

Replaces streak-stats.demolab.com. That service is fine most of the time, but when its
upstream GitHub call fails it returns a "Failed to retrieve contributions" card — and that
error card is a valid 200 SVG served with `cache-control: public, max-age=86400`, so
GitHub's camo proxy caches the failure for a full day. A card that breaks for 24 hours at a
time on a profile shown to admissions committees is not worth the dependency.

Numbers verified against the service before switching: total 703 = 703, longest streak 13
(2026-05-25 -> 2026-06-06) = 13.

    GITHUB_TOKEN=$(gh auth token) python3 tools/streak.py
    python3 tools/streak.py --check      # exit 1 if the SVGs are stale
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contrib import THEMES, graphql, fetch_daily  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def pretty(day):
    """2026-05-25 -> 'May 25'."""
    y, m, d = day.split("-")
    return "%s %d" % (MONTH_ABBR[int(m) - 1], int(d))


def streaks(daily, today):
    """(total, current, current_range, longest, longest_range) from {date: count}."""
    days = sorted(daily)
    total = sum(daily.values())

    longest = run = 0
    run_start = l_start = l_end = None
    for d in days:
        if daily[d] > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, l_start, l_end = run, run_start, d
        else:
            run = 0

    # Today counts as pending, not as a break: a day with no commits yet has not ended.
    i = len(days) - 1
    if days and days[-1] == today and daily[today] == 0:
        i -= 1
    cur = 0
    c_end = None
    while i >= 0 and daily[days[i]] > 0:
        if c_end is None:
            c_end = days[i]
        cur += 1
        i -= 1
    c_start = days[i + 1] if cur else None

    def rng(a, b):
        if not a:
            # A zero streak has no date range. Showing today's date here would make the SVG
            # change every day on its own, which would mean a daily commit that says nothing.
            return "—"
        return pretty(a) if a == b else "%s - %s" % (pretty(a), pretty(b))

    return total, cur, rng(c_start, c_end), longest, rng(l_start, l_end)


def render(theme, total, cur, cur_rng, longest, long_rng, since):
    """Three panels: total / current / longest. Inline fills only — no <style>, no <script>."""
    c = THEMES[theme]
    W, H = 495, 195
    col = W / 3.0
    fam = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
              'role="img" aria-label="Contribution streak">' % (W, H, W, H))
    s.append('<title>%d contributions, current streak %d, longest streak %d</title>'
             % (total, cur, longest))

    for x in (col, col * 2):
        s.append('<line x1="%.1f" y1="38" x2="%.1f" y2="160" stroke="%s" stroke-width="1"/>'
                 % (x, x, c["axis"]))

    # Ring outer edge sits at 75+33+2.5 = 110.5; the label cap-height starts near 121. Keep
    # that gap — at r=37 the ring cut straight through the word "Streak".
    def panel(cx, big, label, sub, ring=False):
        size = 30
        if ring:
            s.append('<circle cx="%.1f" cy="75" r="33" fill="none" stroke="%s" stroke-width="5"/>'
                     % (cx, c["bar"]))
            # The ring can't grow to fit a longer number — at r=37 it cut through the label
            # below — so the number shrinks instead. Total contributions only climbs, and
            # "1,234" at size 30 is wider than the ring's inner width.
            inner = 2 * (33 - 2.5) - 6
            width = sum(0.30 if ch == "," else 0.60 for ch in big) * size
            if width > inner:
                size = int(size * inner / width)
        s.append('<text x="%.1f" y="86" text-anchor="middle" font-family="%s" font-size="%d" '
                 'font-weight="700" fill="%s">%s</text>' % (cx, fam, size, c["bar"], big))
        s.append('<text x="%.1f" y="131" text-anchor="middle" font-family="%s" font-size="14" '
                 'font-weight="600" fill="%s">%s</text>' % (cx, fam, c["title"], label))
        s.append('<text x="%.1f" y="152" text-anchor="middle" font-family="%s" font-size="12" '
                 'fill="%s">%s</text>' % (cx, fam, c["muted"], sub))

    # The ring marks total contributions, not the current streak. A streak resets to 1 or 0
    # on any day off, so circling it emphasises the one number that is mostly noise.
    panel(col * 0.5, "{:,}".format(total), "Total Contributions", since, ring=True)
    panel(col * 1.5, str(cur), "Current Streak", cur_rng)
    panel(col * 2.5, str(longest), "Longest Streak", long_rng)
    s.append("</svg>")
    return "\n".join(s) + "\n"


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token) ...)")
    user = "jackiectl"

    created = graphql(token, '{ user(login: "%s") { createdAt } }' % user)["user"]["createdAt"]
    start = datetime.strptime(created[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    daily = fetch_daily(token, user, start, now)
    today = now.strftime("%Y-%m-%d")
    total, cur, cur_rng, longest, long_rng = streaks(daily, today)
    since = "%s - Present" % pretty(created[:10])

    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)
    stale = False
    for theme in ("dark", "light"):
        svg = render(theme, total, cur, cur_rng, longest, long_rng, since)
        path = os.path.join(ASSETS, "streak-%s.svg" % theme)
        old = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
        if "--check" in sys.argv:
            if old != svg:
                stale = True
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)

    if "--check" in sys.argv:
        print("streak SVGs %s" % ("are STALE — rerun tools/streak.py" if stale else "are up to date"))
        return 1 if stale else 0

    print("wrote streak cards: total=%d  current=%d (%s)  longest=%d (%s)"
          % (total, cur, cur_rng, longest, long_rng))
    return 0


if __name__ == "__main__":
    sys.exit(main())
