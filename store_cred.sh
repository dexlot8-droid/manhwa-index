#!/bin/bash
# Store dexlot8-droid credentials in git credential store
# Token is read from memory file, not typed in command

TOKEN=$(cat /tmp/.dexlot_token 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "No token file found"
    exit 1
fi

printf "protocol=https\nhost=github.com\nusername=dexlot8-droid\npassword=%s\n" "$TOKEN" | git credential-store store
echo "Done. Testing..."
git credential-store get <<EOF
protocol=https
host=github.com
username=dexlot8-droid
EOF
