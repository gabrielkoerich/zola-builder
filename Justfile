# Build docs site for a repository (reads README, generates Zola site, builds)
build repo_path:
    python3 scripts/build.py {{repo_path}}

# Generate site files without running zola build
generate repo_path:
    python3 scripts/build.py {{repo_path}} --no-build

# Serve docs locally with live reload
serve repo_path:
    cd {{repo_path}} && zola serve

# Clean generated files from a repository
clean repo_path:
    python3 scripts/build.py {{repo_path}} --clean
