#!/usr/bin/env python3
"""Render the stats card into assets/stats-{dark,light}.svg.

Replaces the github-readme-stats-action step. That generator is fine, but its row labels are
fixed, and one of them is wrong: it prints "Contributed to (last year)" over a number that
comes from `repositoriesContributedTo`, which has no time window at all. There is no option
to relabel it, so the only way to stop showing a misleading label was to render the card here.

Definitions are copied from the upstream fetcher so the numbers do not silently change:
  stars        sum of stargazers over repositories(ownerAffiliations: OWNER)
  commits      REST search/commits?q=author:<user>  (all time, matching include_all_commits)
  prs          user.pullRequests.totalCount
  issues       open + closed
  contributed  repositoriesContributedTo(COMMIT, ISSUE, PULL_REQUEST, REPOSITORY)  — all time
The rank is a direct port of packages/core/src/calculateRank.ts (MIT).

What the token can see decides what the numbers include: STATS_PAT reaches private repos,
GITHUB_TOKEN does not.

    GITHUB_TOKEN=$(gh auth token) python3 tools/stats.py
    python3 tools/stats.py --check      # exit 1 if the SVGs are stale
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contrib import THEMES, graphql  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "profile.json")
ASSETS = os.path.join(HERE, "assets")

# Octicons (MIT, github/octicons), 16x16 viewBox, drawn at 0.875 scale to sit on the text.
ICONS = {
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97"
            ".719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194"
            "L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z",
    "commit": "M1.643 3.143.427 1.927A.25.25 0 0 0 0 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 0 0"
              ".177-.427L2.715 4.215a6.5 6.5 0 1 1-1.18 4.458.75.75 0 1 0-1.493.154 8.001 8.001 0 1 0"
              "1.6-5.684ZM7.75 4a.75.75 0 0 1 .75.75v3.19l1.72 1.72a.75.75 0 1 1-1.06 1.06l-1.94-1.94"
              "A.75.75 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z",
    "pr": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 "
          "3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 "
          "2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 "
          "0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 "
          "0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z",
    "issue": "M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a"
             "6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z",
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 "
            "0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 "
            "11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 "
            ".25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 "
            "0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
}

THRESHOLDS = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
LEVELS = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]


def exponential_cdf(x):
    return 1 - 2 ** -x


def log_normal_cdf(x):
    return x / (1 + x)


def calculate_rank(all_commits, commits, prs, issues, reviews, stars, followers):
    """Direct port of calculateRank.ts. Keeping the constants identical is the point — a
    home-grown formula would quietly change the letter on the card."""
    commits_median = 1000 if all_commits else 250
    weights = {"commits": 2, "prs": 3, "issues": 1, "reviews": 1, "stars": 4, "followers": 1}
    total_weight = sum(weights.values())

    rank = 1 - (
        weights["commits"] * exponential_cdf(commits / float(commits_median))
        + weights["prs"] * exponential_cdf(prs / 50.0)
        + weights["issues"] * exponential_cdf(issues / 25.0)
        + weights["reviews"] * exponential_cdf(reviews / 2.0)
        + weights["stars"] * log_normal_cdf(stars / 50.0)
        + weights["followers"] * log_normal_cdf(followers / 10.0)
    ) / total_weight

    pct = rank * 100
    for i, t in enumerate(THRESHOLDS):
        if pct <= t:
            return LEVELS[i], pct
    return LEVELS[-1], pct


def fetch(token, user):
    q = """
    { user(login: "%s") {
        name login
        reviews: contributionsCollection { totalPullRequestReviewContributions }
        repositoriesContributedTo(first: 1,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
        pullRequests(first: 1) { totalCount }
        openIssues: issues(states: OPEN) { totalCount }
        closedIssues: issues(states: CLOSED) { totalCount }
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER,
          orderBy: {direction: DESC, field: STARGAZERS}) {
            nodes { stargazers { totalCount } } }
    } }
    """ % user
    u = graphql(token, q)["user"]

    stars = sum(n["stargazers"]["totalCount"] for n in u["repositories"]["nodes"])
    return {
        "name": u["name"] or u["login"],
        "stars": stars,
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["openIssues"]["totalCount"] + u["closedIssues"]["totalCount"],
        "reviews": u["reviews"]["totalPullRequestReviewContributions"],
        "followers": u["followers"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "commits": fetch_all_commits(token, user),
    }


def fetch_all_commits(token, user):
    """All-time commit count, the same REST search the upstream card uses for
    include_all_commits. GraphQL only offers a rolling one-year window."""
    req = urllib.request.Request(
        "https://api.github.com/search/commits?per_page=1&q=author:%s" % user,
        headers={"Accept": "application/vnd.github.cloak-preview",
                 "Authorization": "token " + token,
                 "User-Agent": "jackiectl-profile-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["total_count"]


def render(theme, st, level, pct):
    """Inline fills only — no <style>, no <script>. The upstream card fades its text in from
    opacity 0, which means it is blank for the first moment of every page load."""
    c = THEMES[theme]
    W, H = 467, 195
    fam = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'role="img" aria-label="GitHub statistics">' % (W, H, W, H))
    s.append('<title>%s: %d stars, %d commits, %d pull requests, rank %s</title>'
             % (st["name"], st["stars"], st["commits"], st["prs"], level))

    s.append('<text x="25" y="34" font-family="%s" font-size="16" font-weight="600" fill="%s">'
             "%s's GitHub Stats</text>" % (fam, c["title"], st["name"]))

    rows = [
        ("star",   "Total Stars Earned", st["stars"]),
        ("commit", "Total Commits",      st["commits"]),
        ("pr",     "Total PRs",          st["prs"]),
        ("issue",  "Total Issues",       st["issues"]),
        # No "(last year)": the number has no time window, and saying otherwise was the whole
        # reason this card stopped coming from upstream.
        ("repo",   "Contributed to",     st["contributed"]),
    ]
    y = 70
    for key, label, value in rows:
        s.append('<g transform="translate(25,%d) scale(0.875)" fill="%s">'
                 '<path d="%s"/></g>' % (y - 12, c["bar"], ICONS[key]))
        s.append('<text x="50" y="%d" font-family="%s" font-size="14" font-weight="600" '
                 'fill="%s">%s:</text>' % (y, fam, c["title"], label))
        s.append('<text x="280" y="%d" text-anchor="end" font-family="%s" font-size="14" '
                 'font-weight="600" fill="%s">%s</text>'
                 % (y, fam, c["text"], "{:,}".format(value)))
        y += 25

    # Rank ring. The arc runs clockwise from 12 o'clock, longer for a better percentile.
    cx, cy, r = 370, 100, 40
    s.append('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-width="6"/>'
             % (cx, cy, r, c["bar_dim"]))
    frac = max(0.0, min(1.0, 1 - pct / 100.0))
    circ = 2 * 3.141592653589793 * r
    s.append('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-width="6" '
             'stroke-linecap="round" stroke-dasharray="%.2f %.2f" '
             'transform="rotate(-90 %d %d)"/>'
             % (cx, cy, r, c["bar"], circ * frac, circ, cx, cy))
    s.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="24" '
             'font-weight="700" fill="%s">%s</text>' % (cx, cy + 8, fam, c["title"], level))

    s.append("</svg>")
    return "\n".join(s) + "\n"


def main():
    with open(DATA, encoding="utf-8") as f:
        user = json.load(f)["identity"]["github"]

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token) ...)")

    st = fetch(token, user)
    level, pct = calculate_rank(True, st["commits"], st["prs"], st["issues"],
                                st["reviews"], st["stars"], st["followers"])

    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)
    stale = False
    for theme in ("dark", "light"):
        svg = render(theme, st, level, pct)
        path = os.path.join(ASSETS, "stats-%s.svg" % theme)
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
        print("stats cards %s" % ("are STALE — rerun tools/stats.py" if stale else "are up to date"))
        return 1 if stale else 0

    print("wrote stats cards: stars=%d commits=%d prs=%d issues=%d contributed=%d -> %s (%.1f%%)"
          % (st["stars"], st["commits"], st["prs"], st["issues"], st["contributed"], level, pct))
    return 0


if __name__ == "__main__":
    sys.exit(main())
