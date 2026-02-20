# zola-builder

Generate documentation sites from a repository's README. Reads the markdown, splits it into pages, and produces a [Zola](https://www.getzola.org/) site with a dark theme matching [gabrielkoerich.com](https://gabrielkoerich.com).

## Usage

### Option 1: GitHub Action (Recommended)

Keep your repo clean — just add a workflow file and let CI handle everything.

```bash
just install-workflow ../skills
```

This installs `.github/workflows/zola-builder.yml` in the target repo. The workflow uses this repository as a GitHub Action to build and deploy docs automatically.

You can customize the action reference:

```bash
just install-workflow ../skills --action-ref="your-org/zola-builder@v1"
```

**Custom domains:** If using a custom domain or subdirectory (e.g., `https://example.com/mysite/`), edit the workflow and set `BASE_URL`:

```yaml
env:
  BASE_URL: "https://projects.gabrielkoerich.com/skills"
```

Leave it empty (`""`) for root-relative URLs (`/`) which work with GitHub Pages default domains.

### Option 2: Local Generation

Generate all Zola files directly in the target repo for local development.

```bash
just build ../skills
```

This reads `../skills/README.md`, generates a Zola site in that repo, and builds it. If the path doesn't exist, it prompts for a clone URL.

Other commands:

```bash
just generate ../skills   # generate files without building
just serve ../skills      # live-reload preview
just clean ../skills      # remove generated Zola files
```

## Requirements

- [Zola](https://www.getzola.org/) (static site generator)
- [gh](https://cli.github.com/) (GitHub CLI, for fetching repo metadata)
- [just](https://github.com/casey/just) (task runner)
- Python 3

## What it does

### GitHub Action Mode (Option 1)

Installs a single workflow file that:
1. Uses this repo as a GitHub Action on push to main
2. Builds the docs in CI without polluting the source repo
3. Deploys to GitHub Pages automatically

### Local Mode (Option 2)

1. Extracts metadata from the target repo (name, description, author) via `git` remote and `gh` CLI
2. Parses `README.md` — title from `#`, intro from the first paragraph, pages from each `##` section
3. Fixes cross-page anchor links (rewrites `#anchor` references that point to headings on other pages)
4. Copies the Zola template (templates, sass, static)
5. Generates `config.toml` with repo-specific values
6. Generates `content/` pages with short sidebar titles (first 2 words of each heading)
7. Sets up `.github/workflows/deploy.yml` for GitHub Pages
8. Appends `docs-serve`, `docs-build`, `docs-check` recipes to the target repo's Justfile
9. Adds `public/` to `.gitignore`
10. Runs `zola build` to verify

## What gets created

### GitHub Action Mode

```
.github/workflows/zola-builder.yml   # Single workflow file
```

Everything else happens in CI using this repo as a reusable action.

### Local Mode

```
config.toml                     # Zola config (base_url, title, author)
content/
  _index.md                     # Homepage (intro + doc links)
  quick-start.md                # One page per ## section
  ...
templates/                      # Zola templates (base, index, page)
sass/
  main.scss                     # Dark theme, 800px centered layout
static/
.github/workflows/deploy.yml   # Build + deploy to GitHub Pages
```

## Template

Dark theme inspired by GitHub's color palette. 800px max-width centered container. Doc pages use a 160px sticky sidebar with short titles and a content area.

- Header: `Author Name > Project Name` breadcrumb with GitHub icon
- Homepage: intro text + documentation links
- Doc pages: sidebar nav + content with page title
- Footer: copyright + GitHub link
- Responsive: sidebar collapses to horizontal tags on mobile

## Structure

```
zola-builder/
  action.yml                    # GitHub Action definition
  Justfile                      # just build <repo_path> / just install-workflow <repo_path>
  scripts/
    build.py                    # Main build script (local mode)
    build-action.py             # Build script for GitHub Actions
    install-workflow.py         # Installs workflow in target repo
  template/
    templates/
      base.html                 # Layout with header, sidebar, footer
      index.html                # Homepage
      page.html                 # Doc page with sidebar
    sass/
      main.scss                 # Dark theme styles
    workflows/
      deploy.yml                # GitHub Actions for GitHub Pages (local mode)
      zola-builder.yml          # Workflow using this repo as an action
```
