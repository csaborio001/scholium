#!/bin/sh
# Local, non-destructive installation. Does not modify shell profiles or start services.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$project_dir/.verify/install-tmp" "$project_dir/.verify/pip-cache"
export TMPDIR="$project_dir/.verify/install-tmp"
export PIP_CACHE_DIR="$project_dir/.verify/pip-cache"
if [ ! -x "$project_dir/.venv/bin/python" ]; then
    python3.12 -m venv "$project_dir/.venv"
fi
"$project_dir/.venv/bin/python" -m pip install -e "$project_dir"
"$project_dir/.venv/bin/scholium" --version
printf '\nInstalled. Add this line to your shell settings if needed:\nexport PATH="%s/.venv/bin:$PATH"\n' "$project_dir"
