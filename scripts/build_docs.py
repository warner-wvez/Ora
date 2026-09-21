#!/usr/bin/env python3
"""Check docs/ (numbered markdown), and render it to a static site if asked.

Files are ordered by their numeric prefix (1-overview.md, 1.1-architecture.md, 2-map.md),
slugs drop the prefix, and one subfolder level is allowed (docs/6-decisions/0001-x.md ->
decisions/0001-x). A page declares its type in front matter (type: source|adr|page); each
type has required H2 headings, and --check fails on a missing heading or a link to a file
that does not exist. Links between pages are relative .md paths, because the docs are read
on GitHub; the renderer rewrites them to /docs/<slug> when it builds a site.

    uv run --with markdown python scripts/build_docs.py --check
    uv run --with markdown python scripts/build_docs.py --out docs-site
"""
import argparse, os, re, shutil, sys
from dataclasses import dataclass, field

REQUIRED = {
    "source": ["Where the list comes from", "How images and video are read", "What a camera gives us",
               "Known limits", "Runbook", "Files"],
    "adr": ["Context", "Decision", "Consequences"],
    "page": [],
}
SKIP_DIRS = {"superpowers", "docs-assets"}
PREFIX = re.compile(r"^(\d+(?:\.\d+)*)-")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
H1 = re.compile(r"^# (.+)$", re.M)
H2 = re.compile(r"^## (.+)$", re.M)


@dataclass
class Page:
    rel: str            # path relative to the docs dir, e.g. "6-decisions/0001-x.md"
    slug: str           # "decisions/0001-x"
    title: str
    ptype: str
    text: str           # body without front matter
    key: tuple = field(default_factory=tuple)


def sort_key(name):
    base = os.path.basename(name)
    m = PREFIX.match(base)
    nums = tuple(int(x) for x in m.group(1).split(".")) if m else (10**6,)
    nums = nums + (0,) * (4 - len(nums))      # pad so 1-x sorts before 1.1-x and keys compare int to int
    return nums + (base,)


def slug(name):
    parts = name.replace("\\", "/").split("/")
    out = []
    for i, p in enumerate(parts):
        p = re.sub(r"\.md$", "", p)
        m = PREFIX.match(p)
        is_folder = i < len(parts) - 1
        if m and (is_folder or len(parts) == 1):
            p = p[m.end():]          # "6-decisions" -> "decisions", "3.1-texas" -> "texas"
        out.append(p)
    return "/".join(out)


def split_front(text):
    m = FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def page_type(text):
    meta, _ = split_front(text)
    return meta.get("type", "page")


def missing_headings(text, ptype):
    _, body = split_front(text)
    have = {h.strip() for h in H2.findall(body)}
    return [h for h in REQUIRED.get(ptype, []) if h not in have]


def collect(docs_dir):
    pages = []
    for root, dirs, files in os.walk(docs_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        rel_root = os.path.relpath(root, docs_dir)
        if rel_root != "." and os.sep in rel_root:
            continue                     # one subfolder level only
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            rel = f if rel_root == "." else os.path.join(rel_root, f)
            raw = open(os.path.join(root, f), encoding="utf-8").read()
            meta, body = split_front(raw)
            m = H1.search(body)
            title = m.group(1).strip() if m else slug(rel)
            # a folder sorts right after its own index page ("6-decisions.md" then "6-decisions/...")
            key = sort_key(rel_root + ".md") + sort_key(f) if rel_root != "." else sort_key(f)
            pages.append(Page(rel=rel, slug=slug(rel), title=title, ptype=meta.get("type", "page"), text=body, key=key))
    pages.sort(key=lambda p: p.key)
    return pages


def resolve(page_rel, target):
    """A link target relative to the page's folder, normalised against the docs dir."""
    return os.path.normpath(os.path.join(os.path.dirname(page_rel), target)).replace("\\", "/")


def check_links(pages, docs_dir):
    """Every relative link must land on a docs page or on a file that exists in the repo."""
    known = {p.rel.replace("\\", "/") for p in pages}
    problems = []
    for p in pages:
        for target in LINK.findall(p.text):
            if re.match(r"^[a-z]+:", target):
                continue                 # http(s):, mailto:
            t = resolve(p.rel, target)
            if t in known or os.path.exists(os.path.join(docs_dir, t)):
                continue
            problems.append(f"{p.rel}: link to missing file {target}")
    return problems


def check(pages, docs_dir):
    problems = []
    for p in pages:
        for h in missing_headings(p.text, p.ptype):
            problems.append(f"{p.rel}: missing required heading '## {h}' for type {p.ptype}")
    problems += check_links(pages, docs_dir)
    return problems


CSS = """
:root{--fg:#1b1b1b;--bg:#fff;--muted:#666;--line:#e5e5e5;--link:#0b57d0}
@media (prefers-color-scheme:dark){:root{--fg:#e8e8e8;--bg:#121212;--muted:#9a9a9a;--line:#2a2a2a;--link:#8ab4f8}}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
.wrap{display:grid;grid-template-columns:260px 1fr;min-height:100vh}
nav{border-right:1px solid var(--line);padding:24px 16px;font-size:14px;position:sticky;top:0;height:100vh;overflow:auto;box-sizing:border-box}
nav a{display:block;color:var(--fg);text-decoration:none;padding:3px 6px;border-radius:4px}
nav a.sub{padding-left:18px;color:var(--muted)} nav a.on{background:var(--line)}
main{padding:32px 48px;max-width:860px}
a{color:var(--link)} pre{overflow:auto;padding:12px;border:1px solid var(--line);border-radius:6px}
code{font-size:.92em} table{border-collapse:collapse;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left} h1{margin-top:0}
img{max-width:100%} .meta{color:var(--muted);font-size:13px;margin:32px 0 0}
@media (max-width:900px){.wrap{grid-template-columns:1fr}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}main{padding:20px}}
"""

MERMAID = ('<script type="module">import m from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
           'm.initialize({startOnLoad:true});</script>')


def rewrite_links(page, pages):
    """Relative .md links become /docs/<slug> so the rendered site navigates by slug."""
    by_rel = {p.rel.replace("\\", "/"): p.slug for p in pages}

    def sub(m):
        target, anchor = m.group(1), m.group(2) or ""
        t = resolve(page.rel, target)
        return f"](/docs/{by_rel[t]}{anchor})" if t in by_rel else m.group(0)
    return re.sub(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)", sub, page.text)


def render_md(body):
    import markdown
    body = re.sub(r"```mermaid\n(.*?)```", lambda m: '<pre class="mermaid">\n%s</pre>' % m.group(1), body, flags=re.S)
    return markdown.markdown(body, extensions=["tables", "fenced_code", "toc", "attr_list", "md_in_html"])


def nav_html(pages, current):
    items = []
    for p in pages:
        m = PREFIX.match(os.path.basename(p.rel))
        depth = p.rel.count("/") + (m.group(1).count(".") if m else 0)
        cls = ("sub " if depth else "") + ("on" if p.slug == current else "")
        items.append(f'<a class="{cls.strip()}" href="/docs/{p.slug}">{p.title}</a>')
    return "\n".join(items)


def build(docs_dir, out_dir, repo="https://github.com/warner-wvez/Ora"):
    pages = collect(docs_dir)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    assets = os.path.join(docs_dir, "docs-assets")
    if os.path.isdir(assets):
        shutil.copytree(assets, os.path.join(out_dir, "docs-assets"))
    for p in pages:
        html = render_md(rewrite_links(p, pages))
        edit = f"{repo}/blob/main/docs/{p.rel}"
        doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{p.title} | Ora docs</title><style>{CSS}</style></head><body><div class="wrap">
<nav><a href="/docs/overview"><strong>Ora docs</strong></a>{nav_html(pages, p.slug)}</nav>
<main>{html}<p class="meta"><a href="{edit}">Edit this page on GitHub</a></p></main></div>{MERMAID}</body></html>"""
        folder = os.path.join(out_dir, p.slug)
        os.makedirs(folder, exist_ok=True)
        open(os.path.join(folder, "index.html"), "w", encoding="utf-8").write(doc)
    first = pages[0].slug if pages else "overview"
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(
        f'<!doctype html><meta http-equiv="refresh" content="0; url=/docs/{first}">')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--out", default="docs-site")
    ap.add_argument("--check", action="store_true", help="validate headings and links, do not build")
    a = ap.parse_args()
    pages = collect(a.docs)
    problems = check(pages, a.docs)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)
    if a.check:
        print(f"ok: {len(pages)} pages")
        return
    build(a.docs, a.out)
    print(f"built {len(pages)} pages into {a.out}/")


if __name__ == "__main__":
    main()
