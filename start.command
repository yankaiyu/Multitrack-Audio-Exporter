#!/bin/bash
cd "$(dirname "$0")"
/usr/bin/python3 server.py &
SERVER_PID=$!

# Give the local server a moment to bind before opening the default browser.
sleep 0.5
/usr/bin/open "http://127.0.0.1:8765"

# Keep the Terminal window and the local-only server alive until the user stops it.
wait "$SERVER_PID"
