#!/usr/bin/env python3
"""Render the contribution graph as monthly bars, into assets/contributions-{dark,light}.svg.

Why this exists instead of a card service: every off-the-shelf card plots *daily* bars over
the last ~31 days, and the two hosts we tried (github-readme-stats, github-profile-trophy)
are both dead. This pulls the real numbers from GitHub's GraphQL contributionsCollection and
commits the SVGs, so the README depends on nothing that can go offline.

The window is rolling — it always ends at the current month and reaches back `months` (from
data/profile.json). Regenerated daily by .github/workflows/contributions.yml.

    GITHUB_TOKEN=$(gh auth token) python3 tools/contrib.py
    python3 tools/contrib.py --check      # exit 1 if the SVGs are stale
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "profile.json")
ASSETS = os.path.join(HERE, "assets")

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Warm palette, matched to the gruvbox themes the other two cards use.
THEMES = {
    "dark":  {"bar": "#fabd2f", "bar_dim": "#7c6f64", "title": "#fabd2f",
              "text": "#ebdbb2", "muted": "#a89984", "axis": "#504945"},
    "light": {"bar": "#b57614", "bar_dim": "#d5c4a1", "title": "#b57614",
              "text": "#3c3836", "muted": "#7c6f64", "axis": "#d5c4a1"},
}


def add_months(year, month, delta):
    i = (year * 12 + (month - 1)) + delta
    return i // 12, i % 12 + 1


def month_window(now, months):
    """The `months` calendar months ending at (and including) the current one."""
    y, m = add_months(now.year, now.month, -(months - 1))
    keys = []
    for k in range(months):
        yy, mm = add_months(y, m, k)
        keys.append((yy, mm))
    return keys


def iso(y, m, d, end=False):
    t = "23:59:59Z" if end else "00:00:00Z"
    return "%04d-%02d-%02dT%s" % (y, m, d, t)


def last_day(y, m):
    ny, nm = add_months(y, m, 1)
    from calendar import monthrange
    return monthrange(y, m)[1]


def graphql(token, query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "jackiectl-profile-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit("GraphQL error: %s" % payload["errors"])
    return payload["data"]


def fetch_daily(token, user, start, end):
    """Daily counts for [start, end]. Chunked, because contributionsCollection caps at 1 year."""
    daily = {}
    cur = start
    while cur <= end:
        # Step to the day before the same date next year, so each slice stays under the cap.
        stop = min(datetime(cur.year + 1, cur.month, 1, tzinfo=timezone.utc), end)
        q = """
        { user(login: "%s") {
            contributionsCollection(from: "%s", to: "%s") {
              contributionCalendar {
                weeks { contributionDays { date contributionCount } } } } } }
        """ % (user,
               cur.strftime("%Y-%m-%dT00:00:00Z"),
               stop.strftime("%Y-%m-%dT23:59:59Z"))
        cal = graphql(token, q)["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                daily[d["date"]] = d["contributionCount"]
        if stop >= end:
            break
        cur = stop
    return daily


def render(months, counts, total, theme, user):
    """A bar chart. No <style> and no <script>: GitHub sanitises those out of README SVGs."""
    c = THEMES[theme]
    W, H = 860, 210
    pad_l, pad_r, pad_t, pad_b = 22, 22, 52, 34
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    n = len(months)
    slot = plot_w / float(n)
    bar_w = min(46.0, slot * 0.62)
    peak = max(counts) if counts and max(counts) > 0 else 1

    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img" aria-label="%s">' % (W, H, W, H, "Contributions by month"))
    s.append('<title>%d contributions in the last %d months</title>' % (total, n))

    fam = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
    s.append('<text x="%d" y="26" font-family="%s" font-size="15" font-weight="600" fill="%s">'
             'Contributions by month</text>' % (pad_l, fam, c["title"]))
    s.append('<text x="%d" y="26" text-anchor="end" font-family="%s" font-size="13" fill="%s">'
             '%s total · last %d months</text>' % (W - pad_r, fam, c["muted"], "{:,}".format(total), n))

    base = pad_t + plot_h
    s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1"/>'
             % (pad_l, base + 0.5, W - pad_r, base + 0.5, c["axis"]))

    for i, ((y, m), v) in enumerate(zip(months, counts)):
        cx = pad_l + slot * i + slot / 2.0
        x = cx - bar_w / 2.0
        h = (float(v) / peak) * plot_h if v > 0 else 0.0
        colour = c["bar"] if v > 0 else c["bar_dim"]
        if h < 2 and v > 0:
            h = 2.0
        if v == 0:
            # A visible stub, so an empty month reads as "zero" and not as "missing data".
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="2" rx="1" fill="%s" opacity="0.55"/>'
                     % (x, base - 2, bar_w, colour))
        else:
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>'
                     % (x, base - h, bar_w, h, colour))
        s.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" font-size="11" '
                 'font-weight="600" fill="%s">%d</text>'
                 % (cx, base - h - 6, fam, c["text"] if v else c["muted"], v))
        label = MONTH_ABBR[m - 1]
        s.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" font-size="11" '
                 'fill="%s">%s</text>' % (cx, base + 16, fam, c["muted"], label))
        if m == 1 or i == 0:
            s.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" font-size="9" '
                     'fill="%s">%d</text>' % (cx, base + 27, fam, c["muted"], y))

    s.append("</svg>")
    return "\n".join(s) + "\n"


def main():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    cfg = d["cards"]["contributions"]
    user = d["identity"]["github"]
    n = int(cfg["months"])

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token) ...)")

    now = datetime.now(timezone.utc)
    keys = month_window(now, n)
    y0, m0 = keys[0]
    start = datetime(y0, m0, 1, tzinfo=timezone.utc)

    daily = fetch_daily(token, user, start, now)

    counts = []
    for (y, m) in keys:
        pre = "%04d-%02d-" % (y, m)
        counts.append(sum(v for k, v in daily.items() if k.startswith(pre)))
    total = sum(counts)

    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)
    stale = False
    for theme in ("dark", "light"):
        svg = render(keys, counts, total, theme, user)
        path = os.path.join(ASSETS, "contributions-%s.svg" % theme)
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

    window = "%s %d → %s %d" % (MONTH_ABBR[keys[0][1] - 1], keys[0][0],
                                MONTH_ABBR[keys[-1][1] - 1], keys[-1][0])
    if "--check" in sys.argv:
        print("contribution SVGs %s" % ("are STALE — rerun tools/contrib.py" if stale else "are up to date"))
        return 1 if stale else 0

    print("wrote %d months (%s), %d contributions" % (n, window, total))
    print("  " + "  ".join("%s:%d" % (MONTH_ABBR[m - 1], v) for (_, m), v in zip(keys, counts)))
    return 0



if __name__ == "__main__":
    sys.exit(main())
