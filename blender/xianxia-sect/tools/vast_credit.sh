#!/usr/bin/env bash
# Prints the Vast.ai credit left on the account (never prints the API key).
cd /e/Github/video_editing || exit 1
export VAST_API_KEY="$(grep -E '^\s*VAST_API_KEY\s*=' .env | head -1 | sed -E 's/^\s*VAST_API_KEY\s*=\s*//; s/^["'\'']//; s/["'\'']\s*$//')"
PYTHONIOENCODING=utf-8 python videos/pdoom-xianxia/tools/cloud/vast.py credit
