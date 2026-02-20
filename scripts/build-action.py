#!/usr/bin/env python3
"""zola-builder action: Generate Zola site in a build directory without polluting source repo."""

import os
import re
import shutil
import sys
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BUILDER_DIR / "template"


def main():
    if len(sys.argv) < 2:
        print("Usage: build-action.py <source_repo_path>", file=sys.stderr)
        sys.exit(1)

    source_path = Path(sys.argv[1]).resolve()
    build_dir = source_path / ".zola-build"

    if not source_path.exists():
        print(f"Error: {source_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    readme_path = source_path / "README.md"
    if not readme_path.exists():
        print(f"Error: No README.md found in {source_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Building docs for: {source_path.name}")

    # Get metadata from GitHub Actions environment
    metadata = get_repo_metadata(source_path)
    readme_data = parse_readme(readme_path)

    print(f"  Title: {readme_data['title']}")
    print(f"  Sections: {len(readme_data['sections'])}")

    # Clean and create build directory
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    # Copy template files to build directory
    copy_template_files(build_dir)

    # Generate config and content in build directory
    generate_config(build_dir, metadata, readme_data)
    generate_content(build_dir, readme_data, source_path)

    print(f"  Generated site in {build_dir}")


def get_repo_metadata(source_path):
    """Extract repository metadata from GitHub Actions environment or git."""
    metadata = {"name": source_path.name, "description": ""}

    # Try GitHub Actions environment first
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if gh_repo and "/" in gh_repo:
        parts = gh_repo.split("/")
        metadata["github_owner"] = parts[0]
        metadata["name"] = parts[1]
        metadata["github_url"] = f"https://github.com/{gh_repo}"
    else:
        # Fallback to git remote
        import subprocess
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=source_path, capture_output=True, text=True,
            )
            if result.returncode == 0:
                remote = result.stdout.strip()
                if "github.com" in remote:
                    # Handle both SSH and HTTPS
                    remote = remote.replace("git@github.com:", "https://github.com/")
                    remote = remote.rstrip("/").removesuffix(".git")
                    parts = remote.split("/")
                    metadata["github_owner"] = parts[-2]
                    metadata["name"] = parts[-1]
                    metadata["github_url"] = remote
        except Exception:
            pass

    # Read description from GitHub env or leave empty
    metadata["description"] = os.environ.get("GITHUB_REPOSITORY_DESCRIPTION", "")

    return metadata


def parse_readme(readme_path):
    """Parse README.md into title, intro, and sections split by ## headings."""
    content = readme_path.read_text()
    lines = content.split("\n")

    result = {"title": "", "intro": "", "sections": []}

    i = 0
    # Find title (first # heading)
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            result["title"] = stripped[2:].strip()
            i += 1
            break
        i += 1

    # Collect intro (everything before first ##)
    intro_lines = []
    while i < len(lines):
        if lines[i].strip().startswith("## "):
            break
        intro_lines.append(lines[i])
        i += 1
    result["intro"] = "\n".join(intro_lines).strip()

    # Split by ## headings into sections
    current = None
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("## "):
            if current:
                current["content"] = "\n".join(current["_lines"]).strip()
                del current["_lines"]
                result["sections"].append(current)
            title = line.strip()[3:].strip()
            current = {"title": title, "slug": slugify(title), "_lines": []}
        elif current is not None:
            current["_lines"].append(line)
        i += 1

    if current:
        current["content"] = "\n".join(current["_lines"]).strip()
        del current["_lines"]
        result["sections"].append(current)

    return result


def slugify(text):
    """Convert text to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def escape_toml(s):
    """Escape a string for use in a TOML quoted value."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def short_title(title, max_words=2):
    """Generate a short sidebar title from the first N words."""
    words = title.split()
    if len(words) <= max_words:
        return title
    return " ".join(words[:max_words])


def build_heading_map(readme_data):
    """Build a map of heading_id -> page_slug for all headings across all pages."""
    heading_map = {}

    # Headings in intro (homepage)
    for line in readme_data["intro"].split("\n"):
        m = re.match(r"^(#{2,6})\s+(.+)", line.strip())
        if m:
            heading_map[slugify(m.group(2))] = None  # None = homepage

    # Headings in each section
    for section in readme_data["sections"]:
        # The section's own title as a heading
        heading_map[section["slug"]] = section["slug"]
        # Sub-headings within the section
        for line in section["content"].split("\n"):
            m = re.match(r"^(#{2,6})\s+(.+)", line.strip())
            if m:
                heading_map[slugify(m.group(2))] = section["slug"]

    return heading_map


def fix_anchor_links(content, current_slug, heading_map):
    """Rewrite internal #anchor links to cross-page @/ links or strip broken ones."""
    def replace_link(match):
        full = match.group(0)
        text = match.group(1)
        anchor = match.group(2)

        if anchor not in heading_map:
            # Broken anchor - return just the text
            return text

        target_slug = heading_map[anchor]
        if target_slug == current_slug:
            return full  # Same page, keep as-is

        if target_slug is None:
            # Points to homepage
            return f"[{text}](/#{anchor})"

        return f"[{text}](@/{target_slug}.md#{anchor})"

    return re.sub(r"\[([^\]]+)\]\(#([^)]+)\)", replace_link, content)


def copy_template_files(build_dir):
    """Copy Zola template, sass files to build directory."""
    print("  Copying template files...")
    for subdir in ["templates", "sass"]:
        src = TEMPLATE_DIR / subdir
        dst = build_dir / subdir
        shutil.copytree(src, dst)

    # Create empty static directory
    static_dir = build_dir / "static"
    static_dir.mkdir(exist_ok=True)


def generate_config(build_dir, metadata, readme_data):
    """Generate Zola config.toml in build directory."""
    print("  Generating config.toml...")
    title = escape_toml(readme_data["title"] or metadata["name"])
    description = escape_toml(metadata["description"] or readme_data["intro"][:200])

    # Allow overriding base_url from environment
    base_url = os.environ.get("INPUT_BASE_URL", "")
    if not base_url and metadata.get("github_owner"):
        base_url = f"https://{metadata['github_owner']}.github.io/{metadata['name']}"
    elif not base_url:
        base_url = "http://localhost:1111"

    author = escape_toml(metadata.get("author_name", metadata.get("github_owner", "")))
    author_url = metadata.get("author_website", "")
    if not author_url and metadata.get("github_owner"):
        author_url = f"https://github.com/{metadata['github_owner']}"

    config = f'''base_url = "{base_url}"
compile_sass = true
build_search_index = true
title = "{title}"
description = "{description}"
default_language = "en"
minify_html = true

[extra]
github_url = "{metadata.get('github_url', '')}"
author = "{author}"
author_url = "{author_url}"
'''
    (build_dir / "config.toml").write_text(config)


def generate_content(build_dir, readme_data, source_path):
    """Generate Zola content directory from parsed README sections."""
    print("  Generating content...")
    content_dir = build_dir / "content"
    content_dir.mkdir()

    heading_map = build_heading_map(readme_data)

    # Root section (homepage)
    title = escape_toml(readme_data["title"])
    intro = fix_anchor_links(readme_data["intro"], None, heading_map)
    index_md = f"""+++
title = "{title}"
sort_by = "weight"
template = "index.html"
+++

{intro}
"""
    (content_dir / "_index.md").write_text(index_md)

    # Pages from ## sections
    for i, section in enumerate(readme_data["sections"]):
        section_title = escape_toml(section["title"])
        sidebar_title = escape_toml(short_title(section["title"]))
        content = fix_anchor_links(section["content"], section["slug"], heading_map)
        page_md = f"""+++
title = "{section_title}"
weight = {i + 1}

[extra]
short_title = "{sidebar_title}"
+++

{content}
"""
        (content_dir / f"{section['slug']}.md").write_text(page_md)

    print(f"  Generated {len(readme_data['sections']) + 1} pages")


if __name__ == "__main__":
    main()
