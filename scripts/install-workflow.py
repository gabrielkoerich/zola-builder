#!/usr/bin/env python3
"""Install zola-builder GitHub workflow into a target repository."""

import shutil
import sys
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_WORKFLOW = BUILDER_DIR / "template" / "workflows" / "zola-builder.yml"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Install zola-builder workflow into a target repo")
    parser.add_argument("repo_path", help="Path to the target repository")
    parser.add_argument("--action-ref", default="gabrielkoerich/zola-builder@main",
                        help="The action reference to use (default: gabrielkoerich/zola-builder@main)")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist.")
        sys.exit(1)

    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a git repository.")
        sys.exit(1)

    # Check for README.md
    if not (repo_path / "README.md").exists():
        print(f"Warning: No README.md found in {repo_path}")
        response = input("Continue anyway? [y/N]: ").strip().lower()
        if response != "y":
            sys.exit(1)

    # Create workflows directory
    workflows_dir = repo_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Read the workflow template
    workflow_content = TEMPLATE_WORKFLOW.read_text()

    # Replace the action reference if needed
    if args.action_ref != "gabrielkoerich/zola-builder@main":
        workflow_content = workflow_content.replace(
            "uses: gabrielkoerich/zola-builder@main",
            f"uses: {args.action_ref}"
        )

    # Write the workflow file
    workflow_path = workflows_dir / "zola-builder.yml"
    workflow_path.write_text(workflow_content)

    print(f"Installed workflow to: {workflow_path}")
    print(f"\nAction reference: {args.action_ref}")
    print("\nNext steps:")
    print(f"  1. Commit the workflow: git add .github/workflows/zola-builder.yml && git commit -m 'Add docs workflow'")
    print(f"  2. Push to GitHub: git push")
    print(f"  3. Enable GitHub Pages in repo settings (Source: GitHub Actions)")
    print(f"  4. Your docs will be available at: https://<your-username>.github.io/{repo_path.name}/")


if __name__ == "__main__":
    main()
