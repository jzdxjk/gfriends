#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

# Preserve the existing full-scan behavior for local flags such as
# --refresh-timestamps, while allowing GitHub Actions to select the incremental
# mode with an explicit revision range.
mode_selected=false
for argument in "$@"; do
    case "${argument}" in
        --all|--full-scan|--changed-from|--changed-from=*|--changed-to|--changed-to=*|-h|--help)
            mode_selected=true
            break
            ;;
    esac
done

if [ "${mode_selected}" = false ]; then
    set -- --all "$@"
fi

python3 scripts/update_filetree.py "$@"
