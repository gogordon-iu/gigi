#!/usr/bin/env bash
# close_update_popup.sh
# Kills common Ubuntu GUI update/upgrade notifier processes and optionally disables/removes them.
# Usage:
#   sudo ./close_update_popup.sh [--dry-run] [--force] [--disable-services] [--remove-packages] [--kill-power-manager]
#
# Examples:
#   sudo ./close_update_popup.sh --force --disable-services --remove-packages

set -u

DRY_RUN=false
FORCE=false
DISABLE_SERVICES=false
REMOVE_PACKAGES=false
KILL_POWER_MANAGER=false

# Patterns of processes to target
PATTERNS=(
  "check-new-release-gtk"
  "update-notifier"
  "update-manager"
  "software-properties-gtk"
  "aptdaemon"
  "zenity"
  "gnome-software"
)
# optionally include power manager (xfce4-power-manager) if requested
POWER_MANAGER_PATTERN="xfce4-power-manager"

# Packages to remove (only if --remove-packages)
PACKAGES_TO_REMOVE=(
  "ubuntu-release-upgrader-gtk"
  "update-notifier"
)

# Services to disable (best-effort; may not exist on all systems)
SERVICES_TO_DISABLE=(
  "update-notifier.service"
  "update-manager.service"
  "aptdaemon.service"
)

# helpers
run() {
  if $DRY_RUN; then
    echo "[DRY-RUN] $*"
  else
    echo "+ $*"
    eval "$@"
  fi
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "This script requires root. Re-running with sudo..."
    exec sudo bash "$0" "$@"
  fi
}

# parse args
while (( "$#" )); do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --force) FORCE=true; shift ;;
    --disable-services) DISABLE_SERVICES=true; shift ;;
    --remove-packages) REMOVE_PACKAGES=true; shift ;;
    --kill-power-manager) KILL_POWER_MANAGER=true; shift ;;
    -h|--help)
      cat <<EOF
Usage: sudo ./close_update_popup.sh [options]

Options:
  --dry-run            Print actions that would be taken (don't execute).
  --force              Force-kill (-9) any processes still running after a graceful kill.
  --disable-services   Attempt to disable related systemd services (best-effort).
  --remove-packages    Remove GUI updater packages (non-interactive apt remove -y).
  --kill-power-manager Also target xfce4-power-manager (may disable desktop power features).
  -h, --help           Show this help.

EOF
      exit 0
      ;;
    *) echo "Unknown arg: $1"; shift ;;
  esac
done

# If not dry-run, ensure running as root (for pkill/systemctl/apt)
if ! $DRY_RUN; then
  if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root privileges. Please run with sudo."
    exit 1
  fi
fi

echo "=== close_update_popup.sh starting ==="
echo "Options: dry-run=$DRY_RUN force=$FORCE disable-services=$DISABLE_SERVICES remove-packages=$REMOVE_PACKAGES kill-power-manager=$KILL_POWER_MANAGER"
echo

# Build final pattern list
TARGET_PATTERNS=("${PATTERNS[@]}")
if $KILL_POWER_MANAGER; then
  TARGET_PATTERNS+=("$POWER_MANAGER_PATTERN")
fi

# Find and kill processes
KILLED_ANY=false
for pat in "${TARGET_PATTERNS[@]}"; do
  # use pgrep -f to match the full command line
  pids=$(pgrep -f "$pat" || true)
  if [ -n "$pids" ]; then
    echo "Found processes matching \"$pat\": $pids"
    for pid in $pids; do
      # skip pid 1 and the current shell
      if [ "$pid" -le 1 ]; then
        echo "  skipping PID $pid"
        continue
      fi
      if $DRY_RUN; then
        echo "  [DRY-RUN] would kill $pid ($pat)"
      else
        echo "  killing $pid ($pat) with SIGTERM..."
        if kill "$pid" 2>/dev/null; then
          KILLED_ANY=true
        else
          echo "    failed to send SIGTERM to $pid (maybe already gone)"
        fi
      fi
    done
  else
    echo "No processes found for pattern \"$pat\"."
  fi
done

# Wait a few seconds for graceful exit
if ! $DRY_RUN; then
  sleep 2
fi

# Force-kill remaining matching processes if requested or if some remain
if $FORCE || ! $DRY_RUN; then
  # check which still exist
  still_exists=false
  for pat in "${TARGET_PATTERNS[@]}"; do
    if pgrep -f "$pat" >/dev/null 2>&1; then
      still_exists=true
    fi
  done

  if $still_exists; then
    if $FORCE; then
      echo "Force-killing remaining processes matching target patterns..."
      for pat in "${TARGET_PATTERNS[@]}"; do
        if pgrep -f "$pat" >/dev/null 2>&1; then
          run "pkill -9 -f '$pat' || true"
        fi
      done
    else
      echo "Some processes may still be running. Use --force to send SIGKILL if you want to force them."
    fi
  else
    echo "No remaining target processes detected."
  fi
fi

# Optionally disable services (best-effort)
if $DISABLE_SERVICES; then
  echo
  echo "Attempting to disable related systemd services (best-effort)..."
  for svc in "${SERVICES_TO_DISABLE[@]}"; do
    # Check if the service unit exists
    if systemctl list-unit-files --type=service | grep -q "^${svc}"; then
      echo "Disabling and stopping $svc"
      run "systemctl disable --now '$svc' || true"
    else
      # try without .service suffix if provided
      base="${svc%.service}"
      if systemctl list-unit-files --type=service | grep -q "^${base}.service"; then
        echo "Disabling and stopping ${base}.service"
        run "systemctl disable --now '${base}.service' || true"
      else
        echo "  service $svc not found, skipping."
      fi
    fi
  done
fi

# Optionally remove packages
if $REMOVE_PACKAGES; then
  echo
  echo "Removing GUI upgrader packages (APT) — packages: ${PACKAGES_TO_REMOVE[*]}"
  # update apt cache first (non-interactive)
  run "apt-get update -y || true"
  for pkg in "${PACKAGES_TO_REMOVE[@]}"; do
    # only attempt remove if installed
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      echo "Removing package: $pkg"
      run "DEBIAN_FRONTEND=noninteractive apt-get remove -y '$pkg' || true"
    else
      echo "Package $pkg not installed, skipping."
    fi
  done
  # optionally autoremove
  run "DEBIAN_FRONTEND=noninteractive apt-get autoremove -y || true"
fi

echo
echo "Done. Summary:"
if $DRY_RUN; then
  echo "  (Dry run — no actual kills/changes were performed.)"
else
  if $KILLED_ANY; then
    echo "  Some target processes were killed."
  else
    echo "  No matching processes were found or killed."
  fi
fi

echo "If you still see the popup, check with:"
echo "  ps aux | grep -E 'check-new-release-gtk|update-notifier|update-manager|zenity|aptdaemon'"
echo
echo "=== finished ==="