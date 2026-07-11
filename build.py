#!/usr/bin/env python3
"""Render README.md from data/profile.json.

README.md is generated — edit data/profile.json (and PROFILE.md upstream), never the
README itself. Adding a project or a timeline row must never require touching this file:
everything here loops over the data (CLAUDE.md 铁律 B).

    python3 build.py            # write README.md
    python3 build.py --check    # exit 1 if README.md is stale (for CI)
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "profile.json")
OUT = os.path.join(HERE, "README.md")

SHIELD = "https://img.shields.io/badge/"


def themed_card(card, user):
    """A card that follows the reader's light/dark mode.

    GitHub strips <style> and class attributes from READMEs, so prefers-color-scheme has
    to be expressed structurally: <picture> + a media-scoped <source> is the only hook
    that survives. Without this the dark-theme SVG renders dark-on-white for light-mode
    readers, which is roughly half of them.
    """
    q = card["query"].replace("{u}", user)
    sep = "&" if "?" in card["base"] else "?"
    dark = "%s%s%s&theme=%s" % (card["base"], sep, q, card["theme_dark"])
    light = "%s%s%s&theme=%s" % (card["base"], sep, q, card["theme_light"])
    alt = card["alt"].replace("{u}", user)
    # Pinning height keeps the two side-by-side cards, which come from different services
    # with different native heights, from rendering ragged.
    h = ' height="%s"' % card["height"] if card.get("height") else ""
    return (
        '<picture>\n'
        '  <source media="(prefers-color-scheme: dark)" srcset="%s">\n'
        '  <img alt="%s"%s src="%s">\n'
        '</picture>' % (dark, alt, h, light)
    )


def build(d):
    ident, brand, cards = d["identity"], d["brand"], d["cards"]
    user = ident["github"]
    L = []
    add = L.append

    # ---- header -------------------------------------------------------------
    add('<div align="center">')
    add("")
    add("# %s" % ident["display"])
    add("")
    add("**%s** · %s" % (ident["role"], ident["affiliation"]))
    add("")
    add("`%s`" % brand["meme"])
    add("")
    badges = ['<img alt="Profile views" src="%s">' % cards["views"].replace("{u}", user),
              '<img alt="Followers" src="%s">' % cards["followers"].replace("{u}", user)]
    for link in d["links"]:
        badges.append('<a href="%s"><img alt="%s" src="%s%s"></a>'
                      % (link["url"], link["label"], SHIELD, link["badge"]))
    add("\n".join(badges))
    add("")
    add("</div>")
    add("")
    add(d["bio"])
    add("")

    # ---- stats --------------------------------------------------------------
    add("## GitHub")
    add("")
    add('<div align="center">')
    add("")
    add(themed_card(cards["stats"], user))
    add(themed_card(cards["streak"], user))
    add("")
    add(themed_card(cards["graph"], user))
    add("")
    add("</div>")
    add("")

    # ---- timeline -----------------------------------------------------------
    add("## Timeline")
    add("")
    for t in d["timeline"]:
        line = "- `%s` · **%s**" % (t["when"], t["what"])
        if t.get("detail"):
            line += "  \n  %s" % t["detail"]
        add(line)
    # 铁律 B ③: headroom must be *visible*, not a silent gap.
    add("- `…` · *To be continued · 敬請期待*")
    add("")

    # ---- research -----------------------------------------------------------
    # Collapsed by design: this list is expected to reach dozens of entries, and dozens of
    # four-line blurbs is a wall nobody reads. The hook stays visible in the summary line;
    # the detail is one click away.
    add("## Research")
    add("")
    for r in d["research"]:
        add("<details>")
        add("<summary><b>%s</b> — <i>%s</i></summary>" % (r["title"], r["hook"]))
        add("")
        add(r["detail"])
        add("")
        add("</details>")
        add("")
    add("*More steamers on the next cart · 敬請期待*")
    add("")

    # ---- publications: the section exists even when empty (铁律 B ④) ---------
    add("## Publications")
    add("")
    if d["publications"]:
        for p in d["publications"]:
            add("- %s" % p)
    else:
        add("*In preparation.*")
    add("")

    # ---- skills -------------------------------------------------------------
    add("## Skills")
    add("")
    add("| | |")
    add("|:--|:--|")
    for s in d["skills"]:
        add("| **%s** | %s |" % (s["group"], " · ".join(s["items"])))
    add("")

    # ---- links --------------------------------------------------------------
    add("## Elsewhere")
    add("")
    for link in d["links"]:
        add("- [%s](%s)" % (link["label"], link["url"]))
    for c in d["coming_soon"]:
        add("- **%s** — %s *(coming soon)*" % (c["label"], c["what"]))
    add("")

    # ---- footer -------------------------------------------------------------
    add("---")
    add("")
    add('<div align="center">')
    add("")
    add("**%s**" % brand["lab"])
    add("")
    add("%s" % brand["gloss"])
    add("")
    add("<sub>A stack of steamers, reduced along the last dimension, is one %s.</sub>" % ident["display"])
    add("")
    add("</div>")
    add("")
    return "\n".join(L)


def main():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    out = build(d)

    if "--check" in sys.argv:
        cur = ""
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8") as f:
                cur = f.read()
        if cur != out:
            print("README.md is stale — run: python3 build.py")
            return 1
        print("README.md is up to date.")
        return 0

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote %s (%d bytes, %d research, %d timeline rows)"
          % (OUT, len(out.encode("utf-8")), len(d["research"]), len(d["timeline"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
