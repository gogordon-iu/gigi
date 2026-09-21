#!/bin/bash

# Check if a script name was provided
if [ -z "$1" ]; then
  echo "Usage: $0 <script_name.py>"
  exit 1
fi

SCRIPT_NAME=$1

# Find and kill the process
PID=$(ps aux | grep "[p]ython.*$SCRIPT_NAME" | awk '{print $2}')

if [ -z "$PID" ]; then
  echo "No running process found for $SCRIPT_NAME"
else
  echo "Killing process $PID for $SCRIPT_NAME"
  kill -9 $PID
fi
