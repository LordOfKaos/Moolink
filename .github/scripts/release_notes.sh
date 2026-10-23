#!/usr/bin/env bash
# Print release notes for the commit range since the previous release tag.
# Usage: release_notes.sh <new-tag> <repository (owner/name)>
set -euo pipefail

new_tag="$1"
repo="$2"
prev_tag="$(git describe --tags --abbrev=0 --match 'v*' HEAD 2>/dev/null || true)"

if [[ -n "$prev_tag" ]]; then
  range="$prev_tag..HEAD"
  echo "## Changes since $prev_tag"
else
  range="HEAD"
  echo "## Changes"
fi
echo

# One line per commit, oldest first, skipping merge commits.
git log --reverse --no-merges --pretty='- %s (%h)' "$range"

echo
echo "## Install or update"
echo
echo "In HACS, open **Moolink (Hyundai Bluelink)** and download this version, then restart Home Assistant."

if [[ -n "$prev_tag" ]]; then
  echo
  echo "**Full changelog:** https://github.com/$repo/compare/$prev_tag...$new_tag"
fi
