#!/usr/bin/env python3
"""Render an animated contribution snake into assets/contribution-snake-{dark,light}.svg.

The common third-party snake action does not publish a software license, so this repository
uses its own small renderer instead. The contribution counts come from the same GitHub
GraphQL calendar used by the other local cards. The SVG animation is declarative SMIL: no
JavaScript, CSS, remote assets, or runtime API request is needed when somebody opens the
profile.

    GITHUB_TOKEN=$(gh auth token) python3 tools/snake.py
    python3 tools/snake.py --check      # exit 1 if the SVGs are stale
"""

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contrib import fetch_daily  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "profile.json")
ASSETS = os.path.join(HERE, "assets")

PALETTES = {
    "dark": {
        "empty": "#161b22",
        "levels": ("#0e4429", "#006d32", "#26a641", "#39d353"),
        "snake": "#a970ff",
        "snake_tail": "#8957e5",
        "eye": "#ffffff",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ("#9be9a8", "#40c463", "#30a14e", "#216e39"),
        "snake": "#8250df",
        "snake_tail": "#a475f9",
        "eye": "#ffffff",
    },
}


def calendar_window(now):
    """The last 365 days, padded backwards to Sunday like GitHub's calendar grid."""
    end = now.date()
    first = end - timedelta(days=364)
    days_since_sunday = (first.weekday() + 1) % 7
    start = first - timedelta(days=days_since_sunday)
    return start, end


def levels(counts):
    """Map non-zero counts to four density bands using calendar-local quartiles."""
    positive = sorted(v for v in counts.values() if v > 0)
    if not positive:
        return {}
    n = len(positive)
    cuts = [positive[min(n - 1, int(n * q))] for q in (0.25, 0.50, 0.75)]
    result = {}
    for day, value in counts.items():
        if value <= 0:
            result[day] = 0
        elif value <= cuts[0]:
            result[day] = 1
        elif value <= cuts[1]:
            result[day] = 2
        elif value <= cuts[2]:
            result[day] = 3
        else:
            result[day] = 4
    return result


def snake_order(columns):
    """Visit the grid row by row, reversing direction at each edge."""
    order = []
    for row in range(7):
        cols = range(columns) if row % 2 == 0 else range(columns - 1, -1, -1)
        for col in cols:
            order.append((col, row))
    return order


def render(theme, user, counts, start, end):
    c = PALETTES[theme]
    cell, gap = 11, 3
    pitch = cell + gap
    columns = ((end - start).days // 7) + 1
    grid_w = columns * cell + (columns - 1) * gap
    grid_h = 7 * cell + 6 * gap
    width, height = 860, grid_h + 30
    left = (width - grid_w) / 2.0
    top = 15.0
    duration = 14.0
    ordered = snake_order(columns)
    order_index = dict((point, i) for i, point in enumerate(ordered))
    # Main serpentine route plus the right-edge/top-row return that closes the loop.
    route_steps = (len(ordered) - 1) + 6 + (columns - 1)
    colour_levels = levels(counts)

    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img" aria-label="Animated contribution snake for %s">'
             % (width, height, width, height, html.escape(user, quote=True)))
    total = sum(counts.values())
    s.append('<title>%s: %s contributions in the last year</title>'
             % (html.escape(user), "{:,}".format(total)))

    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        col, row = offset // 7, offset % 7
        x, y = left + col * pitch, top + row * pitch
        key = day.strftime("%Y-%m-%d")
        level = colour_levels.get(key, 0)
        colour = c["empty"] if level == 0 else c["levels"][level - 1]
        s.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="2" fill="%s">'
                 % (x, y, cell, cell, colour))
        if level:
            # Start the animation one cycle in the past so every square has a stable phase
            # immediately, rather than waiting fourteen seconds for the first complete pass.
            phase = duration * order_index[(col, row)] / float(route_steps)
            begin = phase - duration
            s.append('<animate attributeName="opacity" values="1;0.18;0.18;1" '
                     'keyTimes="0;0.006;0.92;1" dur="%.1fs" begin="%.3fs" '
                     'repeatCount="indefinite"/>' % (duration, begin))
        s.append('</rect>')

    centers = [(left + col * pitch + cell / 2.0, top + row * pitch + cell / 2.0)
               for col, row in ordered]
    # Close the route by following the right edge up and the top row back. Without this
    # return leg, a looping animation briefly puts the head at the upper-left and its tail
    # at the lower-right, making one snake look like two unrelated purple marks.
    right_top = (left + (columns - 1) * pitch + cell / 2.0, top + cell / 2.0)
    left_top = (left + cell / 2.0, top + cell / 2.0)
    path = ("M " + " L ".join("%.1f %.1f" % point for point in centers)
            + " L %.1f %.1f L %.1f %.1f Z" % (right_top + left_top))

    # The tail uses the same path with small time offsets. Negative starts preload a full
    # snake on the very first frame instead of letting the body appear one piece at a time.
    segment_delay = duration / float(route_steps)
    for i in range(6, 0, -1):
        begin = -duration + i * segment_delay
        opacity = 0.42 + (6 - i) * 0.09
        colour = c["snake_tail"] if i > 3 else c["snake"]
        s.append('<rect x="-5" y="-5" width="10" height="10" rx="3" fill="%s" '
                 'opacity="%.2f"><animateMotion path="%s" dur="%.1fs" begin="%.3fs" '
                 'repeatCount="indefinite" rotate="auto"/></rect>'
                 % (colour, opacity, path, duration, begin))

    s.append('<g><circle cx="0" cy="0" r="6" fill="%s"/>' % c["snake"])
    s.append('<circle cx="2.2" cy="-2.0" r="1.15" fill="%s"/>' % c["eye"])
    s.append('<circle cx="2.2" cy="2.0" r="1.15" fill="%s"/>' % c["eye"])
    s.append('<animateMotion path="%s" dur="%.1fs" begin="-%.1fs" '
             'repeatCount="indefinite" rotate="auto"/></g>' % (path, duration, duration))
    s.append('</svg>')
    return "\n".join(s) + "\n"


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    user = data["identity"]["github"]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token) ...)")

    start_day, end_day = calendar_window(datetime.now(timezone.utc))
    start = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone.utc)
    end = datetime(end_day.year, end_day.month, end_day.day, 23, 59, 59, tzinfo=timezone.utc)
    counts = fetch_daily(token, user, start, end)

    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)
    stale = False
    for theme in ("dark", "light"):
        svg = render(theme, user, counts, start_day, end_day)
        path = os.path.join(ASSETS, "contribution-snake-%s.svg" % theme)
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
        print("contribution snake SVGs %s"
              % ("are STALE - rerun tools/snake.py" if stale else "are up to date"))
        return 1 if stale else 0

    print("wrote contribution snake: %d contributions from %s to %s"
          % (sum(counts.values()), start_day.isoformat(), end_day.isoformat()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
