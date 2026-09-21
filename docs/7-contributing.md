---
type: page
---
# Contributing

How to commit, how to add a state, how to run the checks, how the docs are checked.

## Commit messages

A hook rejects any message that breaks these rules and prints the rule id, what it saw,
and the fix. Enable it once per clone:

```bash
git config core.hooksPath .githooks
```

**Title:** `area: Effect in plain words`, 72 characters or less. The area is the folder a
reader would look in (`builders`, `scripts`, `docs`, `health`, `ci`, `readme`, `repo`, or
`map` for `index.html`). The effect says what is different now, not how it was done, and
never carries a semicolon, an arrow, a percent sign, or a metric pair; those belong in the
body.

- Bad: `Add a bbox to the Texas builder`
- Good: `builders: Stop Texas pinning cameras in the Gulf of Mexico`

**Body,** for any change over 20 lines or 2 files, in this order, skipping what does not
apply: what changed for the reader, why, the numbers, references (`Refs #12`, `builds on
abc1234`), a breaking change on its own paragraph, alternatives tried, what you learned,
how to test it, and the exact error text for anything searchable. Leave out the list of
files touched. Insider terms get one plain-words expansion on first use.

**Never:** em dashes, emoji, generic phrasing (leverage, seamless, robust, delve), spoken
fillers (basically, literally), a third-person author name, or an AI co-author line.
Merge and revert messages are exempt from the title rules.

## Adding a state

Every state has one builder and one six-heading docs page. In order:

1. Find the feed. Open the agency's 511 or camera map with the browser's network panel
   and look for the JSON, GeoJSON, or JavaScript the map itself loads. If it is Castle
   Rock's platform, add a row to `STATES` in `build-states.py` or
   `build-states-graphql.py` and stop here.
2. Write `builders/build-states-<code>.py` with a docstring that names the endpoint, the
   headers it needs, the image and stream URL shapes, and every trap you hit. Standard
   library only. It writes `states/<CODE>.json` relative to the working directory and
   merges its entry into `states/index.json`.
3. Follow the [source rules](3-sources.md): keep every location, drop only invalid rows,
   store URLs as served, and set `video` only after sampling up to eight streams and
   refusing `token=`, `#EXT-X-KEY`, and Referer-locked hosts.
4. Collapse cameras that share a coordinate into one feature with a view each, so pins
   stay clickable. Expand the feed's direction vocabulary to Northbound, Southbound,
   Eastbound, Westbound, Both directions where it has one.
5. Run it from the repo root and open the map locally. Click five pins on satellite and
   confirm each sits on the road it names.
6. Run `python3 scripts/probe-health.py <CODE>` and look at the bad rate. Above about
   30 percent, look for a filter or a URL shape problem before shipping.
7. Write `docs/3.N-<state>.md` with `type: source` and the six headings, alphabetical
   among the bespoke states, and add the state to `BESPOKE` in
   `scripts/refresh_numbers.py`.
8. Run `uv run python scripts/refresh_numbers.py` and the two docs checks below.
9. Commit the builder, the state file, the index, the docs page, and the numbers in one
   commit titled `builders: Add <State> from <agency's feed>`.
10. Watch the next scheduled health sweep include the state.

## Running the checks

```bash
uv run --with markdown --with pytest pytest scripts/test_build_docs.py -q
uv run --with markdown python scripts/build_docs.py --check
uv run python scripts/refresh_numbers.py
```

The first two are what CI runs on every push. The health sweep has no unit tests; its check
is the six-hour run.

## Docs

Pages live in `docs/`, numbered; the number is the reading order and the slug drops it.
Declare `type: source|adr|page` in the front matter. Source pages need six headings,
decision records three; the check fails on a missing heading or a link to a file that does
not exist. Links between pages are relative `.md` paths. A decision is never edited after
acceptance; a new record supersedes it. Update the docs in the same change as the code.
Handoffs, specs, and plans are not docs: they stay local under `docs/superpowers/`, which
is gitignored.
