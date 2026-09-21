#!/usr/bin/env python3
"""Refresh the live numbers in README.md, docs/1-overview.md, and docs/3-sources.md.

Everything is read from the data files already in the repo, so this needs no key and no
network: states/index.json for the 48 state layers, cameras.json and cameras-nyc.json for
the Illinois and New York City layers, and states/health/*.json for the last sweep. It
rewrites the block between <!-- numbers:start --> and <!-- numbers:end --> in the README
and the overview, and the state table between <!-- states:start --> and <!-- states:end -->
in the sources page, then writes docs/numbers.json. Run from the repo root after a builder
or the health sweep changes a count:

    uv run python scripts/refresh_numbers.py
"""
import glob, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NUMBER_FILES = ["README.md", os.path.join("docs", "1-overview.md")]
SOURCES_PAGE = os.path.join("docs", "3-sources.md")

# Which docs page explains each state's feed. Anything not listed is on the shared 511 pages.
DATATABLES = {"FL", "GA", "UT", "PA", "NC", "NV", "AZ", "WI", "ID", "ME", "NH", "VT", "CT", "LA", "AK", "NY"}
GRAPHQL = {"MN", "CO", "IA", "NE", "IN", "KS", "MA"}
BESPOKE = {
    "AL": "3.3-alabama.md", "AR": "3.4-arkansas.md", "CA": "3.5-california.md", "DE": "3.6-delaware.md",
    "HI": "3.7-hawaii.md", "KY": "3.9-kentucky.md", "MD": "3.11-maryland.md", "MI": "3.12-michigan.md",
    "MS": "3.13-mississippi.md", "MO": "3.14-missouri.md", "MT": "3.15-montana.md", "NM": "3.16-new-mexico.md",
    "ND": "3.18-north-dakota.md", "OH": "3.19-ohio.md", "OK": "3.20-oklahoma.md", "OR": "3.21-oregon.md",
    "RI": "3.22-rhode-island.md", "SC": "3.23-south-carolina.md", "SD": "3.24-south-dakota.md",
    "TN": "3.25-tennessee.md", "TX": "3.26-texas.md", "VA": "3.27-virginia.md", "WA": "3.28-washington.md",
    "WV": "3.29-west-virginia.md", "WY": "3.30-wyoming.md",
}
CITY_LAYERS = [("Illinois", "cameras.json", "3.8-illinois.md"), ("New York City", "cameras-nyc.json", "3.17-new-york-city.md")]


def load(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))


def page_for(code):
    if code in BESPOKE:
        return BESPOKE[code]
    if code in GRAPHQL:
        return "3.2-511-graphql.md"
    if code in DATATABLES:
        return "3.1-511-datatables.md"
    sys.exit(f"{code} is in states/index.json but no docs page claims it; add it to refresh_numbers.py")


def read_numbers():
    index = load(os.path.join("states", "index.json"))
    states = {code: {"name": e["name"], "cameras": e["count"], "video": bool(e.get("video")), "page": page_for(code)}
              for code, e in index.items()}
    cities = {name: {"cameras": len(load(f)["features"]), "page": page} for name, f, page in CITY_LAYERS}
    health = {"placeholder": 0, "frozen": 0, "offline": 0}
    checked = ""
    for p in glob.glob(os.path.join(ROOT, "states", "health", "*.json")):
        if p.endswith("known-placeholders.json"):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for k in health:
            health[k] += d.get("counts", {}).get(k, 0)
        checked = max(checked, d.get("checked_at", ""))
    total = sum(s["cameras"] for s in states.values()) + sum(c["cameras"] for c in cities.values())
    covered = len(states) + (1 if "Illinois" in cities else 0)      # Illinois is a layer, not an index entry
    return {
        "states_covered": covered,
        "cameras": total,
        "video_states": sum(1 for s in states.values() if s["video"]),
        "cameras_down": sum(health.values()),
        "health": health,
        "last_sweep": checked[:16].replace("T", " ") + " UTC" if checked else "never",
        "states": states,
        "cities": cities,
    }


def numbers_block(n):
    return (
        "<!-- numbers:start -->\n"
        "| States | Cameras | States with live video | Cameras down at the last sweep | Last sweep |\n"
        "|---|---|---|---|---|\n"
        f"| {n['states_covered']} of 50 | {n['cameras']:,} | {n['video_states']} | {n['cameras_down']:,} | {n['last_sweep']} |\n"
        "<!-- numbers:end -->"
    )


def states_block(n):
    rows = ["<!-- states:start -->", "| State | Cameras | Live video | How it is read |", "|---|---|---|---|"]
    entries = [(s["name"], s["cameras"], "yes" if s["video"] else "snapshot", s["page"]) for s in n["states"].values()]
    entries += [(name, c["cameras"], "snapshot", c["page"]) for name, c in n["cities"].items()]
    for name, cams, video, page in sorted(entries):
        title = re.sub(r"^[\d.]+-", "", page)[:-3].replace("-", " ").title().replace("Graphql", "GraphQL").replace("Datatables", "DataTables")
        rows.append(f"| {name} | {cams:,} | {video} | [{title}]({page}) |")
    rows.append("<!-- states:end -->")
    return "\n".join(rows)


def replace_block(rel, start, end, new):
    path = os.path.join(ROOT, rel)
    text = open(path, encoding="utf-8").read()
    out, count = re.subn(re.escape(start) + r".*?" + re.escape(end), new, text, flags=re.S)
    if count != 1:
        sys.exit(f"{rel}: expected one {start} block, found {count}")
    open(path, "w", encoding="utf-8").write(out)
    print(f"updated {rel}")


def main():
    n = read_numbers()
    for rel in NUMBER_FILES:
        replace_block(rel, "<!-- numbers:start -->", "<!-- numbers:end -->", numbers_block(n))
    replace_block(SOURCES_PAGE, "<!-- states:start -->", "<!-- states:end -->", states_block(n))
    summary = {k: v for k, v in n.items() if k not in ("states", "cities")}
    json.dump(summary, open(os.path.join(ROOT, "docs", "numbers.json"), "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
