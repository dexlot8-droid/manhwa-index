#!/bin/bash
# setup_git_auth.sh - Set up git authentication for dexlot8-droid
# Run this once to store credentials

cd /tmp/manhwa-index

# Read token from file
TOKEN=$(cat /tmp/.dexlot_token)

# Store credentials
echo "protocol=https
host=github.com
username=dexlot8-droid
password=${TOKEN}" | git credential-store store

echo "Credentials stored. Testing..."
git credential-store get <<EOF
protocol=https
host=github.com
username=dexlot8-droid
EOF
