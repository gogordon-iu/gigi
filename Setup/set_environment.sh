#!/usr/bin/env bash
# ==============================================================================
# Legacy wrapper redirecting to setup_orangepi.sh
# ==============================================================================
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec bash "$SCRIPT_DIR/setup_orangepi.sh" "$@"