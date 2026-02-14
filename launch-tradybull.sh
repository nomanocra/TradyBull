#!/bin/bash

PROJECT_DIR="/Users/davidduprat/Documents/Dev_local/tradybull"
LOG_FILE="/tmp/tradybull-launch.log"

echo "$(date): Starting TradyBull services..." >> "$LOG_FILE"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start backend if not running
if ! nc -z localhost 8000 2>/dev/null; then
    echo "$(date): Starting backend..." >> "$LOG_FILE"
    cd "$PROJECT_DIR/backend"
    nohup python3 main.py >> /tmp/tradybull-backend.log 2>&1 &
else
    echo "$(date): Backend already running" >> "$LOG_FILE"
fi

# Start frontend if not running
if ! nc -z localhost 3080 2>/dev/null; then
    echo "$(date): Starting frontend..." >> "$LOG_FILE"
    cd "$PROJECT_DIR"
    nohup npm run dev >> /tmp/tradybull-frontend.log 2>&1 &
else
    echo "$(date): Frontend already running" >> "$LOG_FILE"
fi

# Wait for services (max 20 seconds)
for i in {1..20}; do
    if nc -z localhost 8000 2>/dev/null && nc -z localhost 3080 2>/dev/null; then
        echo "$(date): Services ready!" >> "$LOG_FILE"
        exit 0
    fi
    sleep 1
done

echo "$(date): Services starting (may need more time)" >> "$LOG_FILE"
exit 0
