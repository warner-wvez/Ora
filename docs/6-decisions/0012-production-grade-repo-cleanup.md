---
type: adr
---
# 0012. The repo is organised to production grade

Date: 2026-09-21. Status: Accepted.

## Context

The repo grew as a working notebook: 34 scripts at the root next to the one HTML file that
is the product, a 25 KB README written as a diary, two handoff files meant for one person
between sessions, no license, and a commit history in which an AI assistant appeared as a
co-author on 78 commits. A visitor could not tell the app from the tooling, and a public
repo with no license grants no rights. The model is the JOBZE.IO cleanup, itself modelled on
ryOS: numbered docs with one skeleton per page type, one folder per unit, checklist
recipes, a product-first README.

## Decision

- History rewritten once: co-author trailers stripped, handoff files removed from every
  commit. Handoffs, specs, and plans stay on the author's machine (`docs/superpowers/` is
  gitignored); the repo records decisions here.
- PolyForm Noncommercial 1.0.0. `SECURITY.md` explains the two keys that are public by
  design. `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, templates, Dependabot.
- Builders in `builders/`, tooling in `scripts/`, the spike in `research/`. `index.html`
  and every file it fetches stay put, so the live site is untouched.
- Numbered `docs/`, three page types, checked in CI on every push; read on GitHub because
  Pages already serves the map. Numbers in the README are rewritten by a script.
- Every commit, including the health bot's, passes the commit-message gate.

## Consequences

- Community profile 28 to 100. Contributors list shows the author alone.
- Anyone adding a state follows one checklist and writes one six-heading page.
- Folding the Illinois and New York City layers into `states/` remains open; it is a code
  change on the layer config, not a cleanup.
