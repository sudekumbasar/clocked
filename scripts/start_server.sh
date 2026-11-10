#!/bin/sh
# Build the web app and start the server on port 8000 (Sonnet 5.5, real model).
# Run from anywhere:  sh ~/Desktop/App/scripts/start_server.sh
# For trying the app with saved photos, build it with test mode on:
#                     sh ~/Desktop/App/scripts/start_server.sh test
# Stop with Ctrl+C.
set -e
cd "$(dirname "$0")/.."
if [ "$1" = "test" ]; then
  npm --prefix web run build:test
else
  npm --prefix web run build
fi
exec server/.venv/bin/uvicorn clocked.app:create_app --factory --app-dir server --host 127.0.0.1 --port 8000
