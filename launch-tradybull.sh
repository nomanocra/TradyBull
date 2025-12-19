#!/bin/bash

PROJECT_DIR="/Users/davidduprat/Documents/Dev_local/tradybull"

# Load nvm to get access to npm/node
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start backend if not running
if ! lsof -i :8000 > /dev/null 2>&1; then
    cd "$PROJECT_DIR/backend"
    /usr/bin/python3 main.py > /tmp/tradybull-backend.log 2>&1 &
    sleep 3
fi

# Start frontend if not running
if ! lsof -i :3080 > /dev/null 2>&1; then
    cd "$PROJECT_DIR"
    npm run dev > /tmp/tradybull-frontend.log 2>&1 &
    sleep 5
fi

# Launch the UI app
open "$PROJECT_DIR/TradyBullUI-darwin-x64/TradyBullUI.app"
