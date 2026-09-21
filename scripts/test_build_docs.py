import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_docs as bd


def write(d, rel, text):
    path = os.path.join(d, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def test_sort_key_orders_numeric_prefixes():
    names = ["10-privacy.md", "1-overview.md", "2.10-x.md", "2.2-y.md", "1.1-arch.md", "3.3.1-deep.md"]
    assert sorted(names, key=bd.sort_key) == [
        "1-overview.md", "1.1-arch.md", "2.2-y.md", "2.10-x.md", "3.3.1-deep.md", "10-privacy.md"]


def test_slug_drops_number_and_extension():
    assert bd.slug("3.26-texas.md") == "texas"
    assert bd.slug("6-decisions/0004-new-jersey-skipped.md") == "decisions/0004-new-jersey-skipped"


def test_page_type_reads_front_matter_and_defaults():
    assert bd.page_type("---\ntype: source\n---\n# Texas\n") == "source"
    assert bd.page_type("# Plain\n") == "page"


def test_missing_headings_for_source_page():
    text = "---\ntype: source\n---\n# Texas\n\n## Where the list comes from\n\n## Runbook\n"
    assert bd.missing_headings(text, "source") == [
        "How images and video are read", "What a camera gives us", "Known limits", "Files"]


def test_check_links_resolves_relative_paths_and_repo_files():
    with tempfile.TemporaryDirectory() as d:
        write(d, "docs/1-overview.md",
              "# Overview\n[ok](3.26-texas.md) [deep](6-decisions/0001-x.md#context) "
              "[code](../builders/build-states-tx.py) [bad](nope.md) [web](https://example.com)\n")
        write(d, "docs/3.26-texas.md", "---\ntype: source\n---\n# Texas\n[up](../README.md)\n")
        write(d, "docs/6-decisions/0001-x.md", "---\ntype: adr\n---\n# 0001. X\n[back](../1-overview.md)\n")
        write(d, "builders/build-states-tx.py", "# stub\n")
        docs = os.path.join(d, "docs")
        problems = bd.check_links(bd.collect(docs), docs)
        assert problems == ["1-overview.md: link to missing file nope.md",
                            "3.26-texas.md: link to missing file ../README.md"]


def test_build_writes_index_and_rewrites_md_links_to_slugs():
    with tempfile.TemporaryDirectory() as d:
        docs = os.path.join(d, "docs"); out = os.path.join(d, "site")
        write(d, "docs/1-overview.md", "# Overview\n\nSee [arch](1.1-architecture.md).\n\n```mermaid\ngraph TD; A-->B\n```\n")
        write(d, "docs/1.1-architecture.md", "# Architecture\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        bd.build(docs, out)
        assert os.path.exists(os.path.join(out, "index.html"))
        overview = open(os.path.join(out, "overview", "index.html")).read()
        assert 'href="/docs/architecture"' in overview and '<pre class="mermaid">' in overview
        assert "<table>" in open(os.path.join(out, "architecture", "index.html")).read()


def test_folder_index_sorts_before_its_children_and_nav_marks_depth():
    with tempfile.TemporaryDirectory() as d:
        write(d, "1-overview.md", "# Overview\n")
        write(d, "1.1-arch.md", "# Arch\n")
        write(d, "6-decisions.md", "# Decisions\n")
        write(d, "6-decisions/0001-x.md", "---\ntype: adr\n---\n# 0001. X\n\n## Context\n## Decision\n## Consequences\n")
        write(d, "7-contrib.md", "# Contrib\n")
        pages = bd.collect(d)
        assert [p.slug for p in pages] == ["overview", "arch", "decisions", "decisions/0001-x", "contrib"]
        nav = bd.nav_html(pages, "overview")
        assert '<a class="on" href="/docs/overview">' in nav
        assert '<a class="sub" href="/docs/arch">' in nav
        assert '<a class="" href="/docs/decisions">' in nav
        assert '<a class="sub" href="/docs/decisions/0001-x">' in nav
