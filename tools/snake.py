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
from collections import deque
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contrib import fetch_daily  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "profile.json")
ASSETS = os.environ.get("SNAKE_ASSETS", os.path.join(HERE, "assets"))

PALETTES = {
    "dark": {
        "empty": "#161b22",
        "levels": ("#0e4429", "#006d32", "#26a641", "#39d353"),
        "border": "#ffffff0d",
        "snake": "#800080",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ("#9be9a8", "#40c463", "#30a14e", "#216e39"),
        "border": "#1b1f230a",
        "snake": "#800080",
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


def next_directions(body):
    """Prefer continuing straight, then turning, while never reversing into the neck."""
    head, neck = body[0], body[1]
    dx, dy = head[0] - neck[0], head[1] - neck[1]
    return ((dx, dy), (-dy, dx), (dy, -dx), (-dx, -dy))


def shortest_snake_path(body, goals, obstacles, columns):
    """Find a shortest collision-free route from the current four-cell snake to any goal.

    One empty border around the calendar lets the snake route around dense contribution
    clusters. Optional obstacles are supported for deterministic tests and future layouts.
    """
    goals = set(goals)
    obstacles = set(obstacles) - goals
    queue = deque([body])
    parent = {body: None}
    found = None

    while queue:
        state = queue.popleft()
        if state[0] in goals:
            found = state
            break
        head = state[0]
        for dx, dy in next_directions(state):
            nxt = (head[0] + dx, head[1] + dy)
            if not (-1 <= nxt[0] <= columns and -1 <= nxt[1] <= 7):
                continue
            # The last tail cell moves away during this step, so entering it is safe.
            if nxt in state[:-1] or nxt in obstacles:
                continue
            new_state = (nxt, state[0], state[1], state[2])
            if new_state in parent:
                continue
            parent[new_state] = state
            queue.append(new_state)

    if found is None:
        raise RuntimeError("could not route contribution snake to the next target")

    path = []
    state = found
    while parent[state] is not None:
        path.append(state[0])
        state = parent[state]
    path.reverse()
    return path


def plan_route(cell_levels, columns):
    """Build a route that eats contribution cells from light green through dark green."""
    by_level = dict((level, set()) for level in range(1, 5))
    for point, level in cell_levels.items():
        if level:
            by_level[level].add(point)

    # Match the reference's opening pose: four purple blocks above the first grid column,
    # with the large head on the left. The first move turns down into the calendar.
    body = ((0, -1), (1, -1), (2, -1), (3, -1))
    route = [body[0], (0, 0)]
    body = ((0, 0),) + body[:3]
    eaten_at = {}

    for level in range(1, 5):
        remaining = by_level[level]
        if body[0] in remaining:
            remaining.remove(body[0])
            eaten_at[body[0]] = len(route) - 1

        while remaining:
            # The snake may cross a darker square while travelling, but only consumes
            # targets from the current colour stage. This keeps the progress strip moving
            # continuously from light green to dark green without letting dense clusters
            # trap the four-cell body.
            path = shortest_snake_path(body, remaining, set(), columns)
            for point in path:
                route.append(point)
                body = (point, body[0], body[1], body[2])
                if point in remaining:
                    remaining.remove(point)
                    eaten_at[point] = len(route) - 1

    # Return to the exact opening pose before the animation repeats. Approaching from below
    # avoids an immediate reversal while the final four cells line up above the grid.
    path = shortest_snake_path(body, {(4, 0)}, set(), columns)
    for point in path + [(4, -1), (3, -1), (2, -1), (1, -1), (0, -1)]:
        if point in body[:-1]:
            raise RuntimeError("closing route collided with the snake body")
        route.append(point)
        body = (point, body[0], body[1], body[2])

    return route, eaten_at


def render(theme, user, counts, start, end):
    c = PALETTES[theme]
    cell, pitch = 12, 16
    columns = ((end - start).days // 7) + 1
    width, height = 880, 192
    duration = 50.0
    colour_levels = levels(counts)

    cell_levels = {}
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        point = (offset // 7, offset % 7)
        key = day.strftime("%Y-%m-%d")
        cell_levels[point] = colour_levels.get(key, 0)

    route, eaten_at = plan_route(dict(cell_levels), columns)
    route_steps = len(route) - 1
    path = "M " + " L ".join("%d %d" % (col * pitch, row * pitch)
                               for col, row in route)

    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="-16 -32 %d %d" role="img" aria-label="Animated contribution snake for %s">'
             % (width, height, width, height, html.escape(user, quote=True)))
    total = sum(counts.values())
    s.append('<title>%s: %s contributions in the last year</title>'
             % (html.escape(user), "{:,}".format(total)))

    for point in sorted(cell_levels, key=lambda p: (p[0], p[1])):
        col, row = point
        x, y = 2 + col * pitch, 2 + row * pitch
        level = cell_levels[point]
        colour = c["empty"] if level == 0 else c["levels"][level - 1]
        s.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="2" fill="%s" '
                 'stroke="%s" stroke-width="1">'
                 % (x, y, cell, cell, colour, c["border"]))
        if level:
            eaten = eaten_at[point] / float(route_steps)
            before = max(0.0, eaten - 0.0002)
            s.append('<animate attributeName="fill" values="%s;%s;%s;%s;%s" '
                     'keyTimes="0;%.5f;%.5f;0.99;1" dur="%.1fs" begin="-%.1fs" '
                     'repeatCount="indefinite"/>'
                     % (colour, colour, c["empty"], c["empty"], colour,
                        before, eaten, duration, duration))
        s.append('</rect>')

    # The lower strip fills in four colour stages as the corresponding cells are eaten.
    active_count = sum(1 for level in cell_levels.values() if level)
    track_width = columns * pitch
    progress_x = 0.0
    for level in range(1, 5):
        points = [point for point, value in cell_levels.items() if value == level]
        if not points:
            continue
        segment_width = track_width * len(points) / float(active_count)
        stage_start = min(eaten_at[point] for point in points) / float(route_steps)
        stage_end = max(eaten_at[point] for point in points) / float(route_steps)
        stage_end = min(0.985, max(stage_start + 0.001, stage_end))
        s.append('<rect x="%.1f" y="144" width="0" height="12" rx="1" fill="%s">'
                 % (progress_x, c["levels"][level - 1]))
        s.append('<animate attributeName="width" values="0;0;%.1f;%.1f;0" '
                 'keyTimes="0;%.5f;%.5f;0.99;1" dur="%.1fs" begin="-%.1fs" '
                 'repeatCount="indefinite"/></rect>'
                 % (segment_width, segment_width, stage_start, stage_end, duration, duration))
        progress_x += segment_width

    # Four differently sized blocks make the tapered purple snake used by the reference.
    # Drawing the tail first keeps the larger head visible when the route crosses itself.
    pieces = ((14.4, 0.8, 4.5), (12.3, 1.8, 4.1),
              (10.8, 2.6, 3.6), (9.9, 3.0, 3.3))
    segment_delay = duration / float(route_steps)
    for index in range(3, -1, -1):
        size, inset, radius = pieces[index]
        begin = -duration + index * segment_delay
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
                 'fill="%s"><animateMotion path="%s" dur="%.1fs" begin="%.3fs" '
                 'repeatCount="indefinite"/></rect>'
                 % (inset, inset, size, size, radius, c["snake"],
                    path, duration, begin))
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
