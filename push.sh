#!/bin/bash
# push.sh - Push to GitHub using token from environment
# Usage: ./push.sh

cd /tmp/manhwa-index

# Read token from environment variable
if [ -z "$DEXLOT_TOKEN" ]; then
    echo "Error: DEXLOT_TOKEN not set"
    exit 1
fi

# Set remote URL with token
git remote set-url origin "https://dexlot8-droid:${DEXLOT_TOKEN}@github.com/dexlot8-droid/manhwa-index.git"

# Push
git push origin main
