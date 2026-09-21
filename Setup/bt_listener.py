#!/usr/bin/env python3
"""
Gigi Bluetooth & Multi-Transport Script Runner.
Thin compatibility wrapper delegating to gigi.core.daemon.
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import gigi.core.daemon as _daemon
from gigi.core.daemon import (
    main,
    scan_files,
    find_script,
    scan_activity_plans,
    scan_custom_interactions,
    ExecutionManager,
    ConnectionWrapper,
)

active_client = None
execution_manager = _daemon.execution_manager

def get_base_dir():
    return PROJECT_ROOT

def process_command_line(line):
    # Sync patched references if tests patched bt_listener directly
    this_mod = sys.modules[__name__]
    if hasattr(this_mod, "active_client") and this_mod.active_client is not None:
        _daemon.active_client = this_mod.active_client
    if hasattr(this_mod, "execution_manager") and this_mod.execution_manager is not None:
        _daemon.execution_manager = this_mod.execution_manager
    return _daemon.process_command_line(line)

if __name__ == "__main__":
    main()
