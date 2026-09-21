# Contributing

## Before you commit

Install the commit-message hook once per clone:

    git config core.hooksPath .githooks

It rejects a message that breaks the rules below and prints the fix. Never bypass it.

## Commit messages

Title: `area: Effect in plain words`, 72 characters or less. `area` is the folder a
reader would look in: `builders`, `scripts`, `docs`, `health`, `ci`, `readme`, `repo`, or
`map` for `index.html`. The effect says what is different now, not how it was done.

Body, for any change over 20 lines or 2 files: what changed for the reader, why, the
numbers, and references (`Refs #12`, `builds on abc1234`). No file lists, no em dashes,
no emoji, no AI co-author lines. The full guide with examples is
[docs/7-contributing.md](docs/7-contributing.md).

## Adding a state

Follow the ten-step checklist in [docs/7-contributing.md](docs/7-contributing.md). Every
state has one builder under `builders/`, run from the repo root, and one six-heading page
under `docs/`. The rules a builder must follow are in [docs/3-sources.md](docs/3-sources.md).

## Checks

    uv run --with markdown --with pytest pytest scripts/test_build_docs.py -q
    uv run --with markdown python scripts/build_docs.py --check
    uv run python scripts/refresh_numbers.py

The first two run in CI on every push.

## Docs

Pages live in `docs/`, numbered. Declare `type: source|adr|page` in the front matter; the
check fails on a missing required heading or a link to a file that does not exist. Update
the docs in the same change as the code. Planning notes stay local under
`docs/superpowers/`, which is gitignored.
