#!/usr/bin/env python3
"""zola-builder: Generate a Zola documentation site from a repository's README."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BUILDER_DIR / "template"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build a Zola docs site from a repository README")
    parser.add_argument("repo_path", help="Path to the target repository")
    parser.add_argument("--no-build", action="store_true", help="Skip zola build step")
    parser.add_argument("--clean", action="store_true", help="Remove generated Zola files from target repo")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist.")
        url = input("Enter a repository URL to clone (or press Enter to cancel): ").strip()
        if not url:
            sys.exit(1)
        print(f"Cloning {url} into {repo_path}...")
        result = subprocess.run(["git", "clone", url, str(repo_path)])
        if result.returncode != 0:
            sys.exit(1)

    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a git repository.")
        sys.exit(1)

    if args.clean:
        clean(repo_path)
        return

    readme_path = repo_path / "README.md"
    if not readme_path.exists():
        print(f"Error: No README.md found in {repo_path}")
        sys.exit(1)

    # Check zola is available
    if not args.no_build and shutil.which("zola") is None:
        print("Warning: zola not found in PATH, skipping build step")
        args.no_build = True

    print(f"Building docs for: {repo_path.name}")

    metadata = get_repo_metadata(repo_path)
    readme_data = parse_readme(readme_path)

    print(f"  Title: {readme_data['title']}")
    print(f"  Sections: {len(readme_data['sections'])}")

    copy_template_files(repo_path)
    generate_config(repo_path, metadata, readme_data)
    generate_content(repo_path, readme_data)
    setup_github_actions(repo_path)
    setup_justfile(repo_path)
    setup_gitignore(repo_path)

    if not args.no_build:
        print("  Running zola build...")
        result = subprocess.run(["zola", "build"], cwd=repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Build failed:\n{result.stderr}")
            sys.exit(1)
        print("  Build successful!")

    print(f"\nDone! Docs site ready in {repo_path}")
    print(f"  Preview: cd {repo_path} && zola serve")
    if metadata.get("github_url"):
        owner = metadata.get("github_owner", "")
        name = metadata["name"]
        print(f"  Production: https://{owner}.github.io/{name}/")


def get_repo_metadata(repo_path):
    """Extract repository metadata from git remote and GitHub API."""
    metadata = {"name": repo_path.name, "github_url": "", "github_owner": "", "description": ""}

    # Parse git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.returncode == 0:
            remote = result.stdout.strip()
            if remote.startswith("git@github.com:"):
                parts = remote.replace("git@github.com:", "").rstrip(".git").split("/")
                metadata["github_owner"] = parts[0]
                metadata["name"] = parts[1] if len(parts) > 1 else repo_path.name
                metadata["github_url"] = f"https://github.com/{parts[0]}/{parts[1]}"
            elif "github.com" in remote:
                remote = remote.rstrip("/").removesuffix(".git")
                metadata["github_url"] = remote
                parts = remote.split("/")
                metadata["github_owner"] = parts[-2]
                metadata["name"] = parts[-1]
    except Exception:
        pass

    # Fetch repo info and owner name from GitHub API via gh CLI
    if metadata["github_url"]:
        try:
            owner_repo = f"{metadata['github_owner']}/{metadata['name']}"
            result = subprocess.run(
                ["gh", "repo", "view", owner_repo, "--json", "description,homepageUrl,owner"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                metadata["description"] = data.get("description", "") or ""
                metadata["homepage"] = data.get("homepageUrl", "") or ""
                owner = data.get("owner", {})
                if owner.get("login"):
                    metadata["github_owner"] = owner["login"]
        except Exception:
            pass

        # Fetch the owner's display name and website
        try:
            result = subprocess.run(
                ["gh", "api", f"/users/{metadata['github_owner']}", "--jq", "[.name, .blog] | @tsv"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("\t")
                if parts[0]:
                    metadata["author_name"] = parts[0]
                if len(parts) > 1 and parts[1]:
                    blog = parts[1]
                    if not blog.startswith("http"):
                        blog = f"https://{blog}"
                    metadata["author_website"] = blog
        except Exception:
            pass

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


def copy_template_files(repo_path):
    """Copy Zola template, sass, and static files to target repo."""
    print("  Copying template files...")
    for subdir in ["templates", "sass"]:
        src = TEMPLATE_DIR / subdir
        dst = repo_path / subdir
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    static_dst = repo_path / "static"
    static_dst.mkdir(exist_ok=True)
    static_src = TEMPLATE_DIR / "static"
    if static_src.exists():
        for f in static_src.iterdir():
            if f.name != ".gitkeep":
                shutil.copy2(f, static_dst / f.name)


def generate_config(repo_path, metadata, readme_data):
    """Generate Zola config.toml from repo metadata."""
    print("  Generating config.toml...")
    title = escape_toml(readme_data["title"] or metadata["name"])
    description = escape_toml(metadata["description"] or readme_data["intro"][:200])

    if metadata.get("github_owner"):
        base_url = f"https://{metadata['github_owner']}.github.io/{metadata['name']}"
    else:
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
github_url = "{metadata['github_url']}"
author = "{author}"
author_url = "{author_url}"
'''
    (repo_path / "config.toml").write_text(config)


def generate_content(repo_path, readme_data):
    """Generate Zola content directory from parsed README sections."""
    print("  Generating content...")
    content_dir = repo_path / "content"

    if content_dir.exists():
        shutil.rmtree(content_dir)
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


def setup_github_actions(repo_path):
    """Copy the GitHub Actions deploy workflow to the target repo."""
    workflows_dir = repo_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    dst = workflows_dir / "deploy.yml"
    src = TEMPLATE_DIR / "workflows" / "deploy.yml"

    if dst.exists():
        print("  GitHub Actions workflow already exists, overwriting...")
    else:
        print("  Setting up GitHub Actions workflow...")
    shutil.copy2(src, dst)


def setup_justfile(repo_path):
    """Add docs recipes to the target repo's Justfile."""
    justfile = repo_path / "Justfile"

    docs_recipes = """
# Serve docs locally with live reload
docs-serve:
    zola serve

# Build docs
docs-build:
    zola build

# Check docs for broken links
docs-check:
    zola check
"""

    if justfile.exists():
        content = justfile.read_text()
        if "docs-serve" in content:
            print("  Justfile already has docs recipes")
            return
        print("  Appending docs recipes to Justfile...")
        with open(justfile, "a") as f:
            f.write(docs_recipes)
    else:
        print("  Creating Justfile...")
        justfile.write_text(docs_recipes.strip() + "\n")


def setup_gitignore(repo_path):
    """Ensure public/ (Zola output) is in .gitignore."""
    gitignore = repo_path / ".gitignore"
    marker = "public/"

    if gitignore.exists():
        content = gitignore.read_text()
        if marker in content:
            return
        print("  Adding public/ to .gitignore...")
        with open(gitignore, "a") as f:
            f.write(f"\n# Zola build output\n{marker}\n")
    else:
        print("  Creating .gitignore...")
        gitignore.write_text(f"# Zola build output\n{marker}\n")


def clean(repo_path):
    """Remove generated Zola files from the target repository."""
    print(f"Cleaning Zola files from {repo_path.name}...")
    for path in ["templates", "sass", "content", "public", "config.toml"]:
        target = repo_path / path
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"  Removed {path}")
    print("Done!")


if __name__ == "__main__":
    main()
