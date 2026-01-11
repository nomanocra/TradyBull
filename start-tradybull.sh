#!/bin/bash

PROJECT_DIR="/Users/davidduprat/Documents/Dev_local/tradybull"
LOG_FILE="/tmp/tradybull-launcher.log"

echo "$(date): Starting TradyBull..." >> "$LOG_FILE"

# Load nvm to get access to npm/node
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start backend if not running
if ! lsof -i :8000 2>/dev/null | grep LISTEN > /dev/null; then
    echo "$(date): Starting backend..." >> "$LOG_FILE"
    cd "$PROJECT_DIR/backend"
    /usr/bin/python3 main.py >> /tmp/tradybull-backend.log 2>&1 &
    sleep 3
else
    echo "$(date): Backend already running" >> "$LOG_FILE"
fi

# Start frontend if not running
if ! lsof -i :3080 2>/dev/null | grep LISTEN > /dev/null; then
    echo "$(date): Starting frontend..." >> "$LOG_FILE"
    cd "$PROJECT_DIR"
    npm run dev >> /tmp/tradybull-frontend.log 2>&1 &
    sleep 5
else
    echo "$(date): Frontend already running" >> "$LOG_FILE"
fi

echo "$(date): Launching UI..." >> "$LOG_FILE"

# Launch the UI app
open "$PROJECT_DIR/TradyBullUI-darwin-x64/TradyBullUI.app"

echo "$(date): Done" >> "$LOG_FILE"
