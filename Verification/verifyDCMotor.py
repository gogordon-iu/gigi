#!/usr/bin/env python3
"""
motor_speed.py

Simple L298N control using gpioset for GPIO toggles plus software PWM.

Usage:
  python3 motor_speed.py             # demo: forward 3s -> reverse 3s -> pwm ramp -> stop
  python3 motor_speed.py forward 5   # forward for 5 seconds (full speed)
  python3 motor_speed.py reverse 2   # reverse for 2 seconds (full speed)
  python3 motor_speed.py stop        # immediate stop (ENA=0, IN1=0, IN2=0)
  python3 motor_speed.py pwm 60 10   # run forward at 60% duty for 10s (software PWM)
  python3 motor_speed.py pwmrev 40 8 # run reverse at 40% duty for 8s
  python3 motor_speed.py ramp 0 80 5 # ramp forward from 0%->80% over 5s
  python3 motor_speed.py ramprev 80 0 6 # ramp reverse 80%->0% over 6s

Notes:
 - CHIP and line numbers are configured below (change if needed).
 - Software PWM toggles ENA by calling 'gpioset' frequently. It's fine for hobby motors,
   but not as smooth as hardware PWM.
 - Ensure L298N GND, battery negative, and Orange Pi GND are common.
"""

import subprocess
import time
import sys
from signal import signal, SIGINT

# --- CONFIGURATION (adjust if your wiring differs) ---
CHIP = "/dev/gpiochip4"   # explicit device path (safe)
IN1 = 10                  # line offset for IN1 (GPIO4_B2)
IN2 = 11                  # line offset for IN2 (GPIO4_B3)
ENA = 16                  # line offset for ENA (GPIO4_C0)
# PWM default period (seconds). 0.02 -> 50 Hz (period = 20 ms)
DEFAULT_PERIOD = 0.02
# ----------------------------------------------------

def gpioset_pairs(pairs):
    """Call gpioset for multiple line=value pairs at once."""
    args = [CHIP] + [f"{line}={1 if val else 0}" for line, val in pairs]
    cmd = ["gpioset"] + args
    subprocess.run(cmd, check=True)

def gpioset_single(line, val):
    """Set a single line using gpioset (subprocess)."""
    subprocess.run(["gpioset", CHIP, f"{line}={1 if val else 0}"], check=True)

def stop():
    """Stop motor and clear direction pins."""
    try:
        gpioset_pairs([(ENA, 0), (IN1, 0), (IN2, 0)])
    except subprocess.CalledProcessError:
        pass

def forward(duration_s=3):
    """Run forward at full speed for duration_s seconds."""
    gpioset_pairs([(IN1, 1), (IN2, 0), (ENA, 1)])
    try:
        time.sleep(duration_s)
    finally:
        gpioset_single(ENA, 0)

def reverse(duration_s=3):
    """Run reverse at full speed for duration_s seconds."""
    gpioset_pairs([(IN1, 0), (IN2, 1), (ENA, 1)])
    try:
        time.sleep(duration_s)
    finally:
        gpioset_single(ENA, 0)

def pwm(direction, duty, duration_s, period=DEFAULT_PERIOD):
    """
    Software PWM on ENA while holding direction.
    direction: "forward" or "reverse"
    duty: 0..100 percent
    duration_s: seconds to run
    period: PWM period in seconds (default 0.02)
    """
    if duty <= 0:
        # no need to toggle, just ensure ENA=0
        if direction == "forward":
            gpioset_pairs([(IN1,1),(IN2,0),(ENA,0)])
        else:
            gpioset_pairs([(IN1,0),(IN2,1),(ENA,0)])
        time.sleep(duration_s)
        return
    if duty >= 100:
        # full on
        if direction == "forward":
            gpioset_pairs([(IN1,1),(IN2,0),(ENA,1)])
        else:
            gpioset_pairs([(IN1,0),(IN2,1),(ENA,1)])
        time.sleep(duration_s)
        gpioset_single(ENA, 0)
        return

    on_time = period * (duty / 100.0)
    off_time = period - on_time
    end = time.time() + duration_s

    # set direction once
    if direction == "forward":
        gpioset_pairs([(IN1,1),(IN2,0)])
    else:
        gpioset_pairs([(IN1,0),(IN2,1)])

    try:
        while time.time() < end:
            if on_time > 0:
                gpioset_single(ENA, 1)
                time.sleep(on_time)
            if off_time > 0:
                gpioset_single(ENA, 0)
                time.sleep(off_time)
    finally:
        gpioset_single(ENA, 0)

def ramp(direction, start_duty, end_duty, duration_s, steps=20, period=DEFAULT_PERIOD):
    """
    Ramp duty smoothly from start_duty -> end_duty over duration_s seconds.
    steps: number of intermediate duty steps to use.
    """
    start_duty = max(0, min(100, float(start_duty)))
    end_duty = max(0, min(100, float(end_duty)))
    if duration_s <= 0 or steps <= 1:
        # immediate set
        pwm(direction, end_duty, 0.5, period)
        return

    # compute per-step duration
    total_steps = int(steps)
    step_duration = duration_s / total_steps
    for i in range(total_steps + 1):
        t = i / total_steps
        duty = start_duty + (end_duty - start_duty) * t
        # run a short PWM burst at this duty
        pwm(direction, duty, step_duration, period)

# Ctrl-C handler to ensure motor stops
def _sigint_handler(sig, frame):
    print("\nInterrupted. Stopping motor...")
    stop()
    sys.exit(0)

signal(SIGINT, _sigint_handler)

def demo():
    print("Demo: forward 3s, reverse 3s, PWM ramp 0->80%, stop")
    forward(3)
    time.sleep(1)
    reverse(3)
    time.sleep(1)
    print("PWM ramp forward 0->80% over 5s")
    ramp("forward", 0, 80, 5, steps=25)
    stop()
    print("Demo done")

def usage():
    print(__doc__)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    try:
        if cmd in ("f", "forward"):
            dur = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
            forward(dur)
        elif cmd in ("r", "reverse"):
            dur = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
            reverse(dur)
        elif cmd in ("s", "stop"):
            stop()
        elif cmd in ("pwm",):
            duty = float(sys.argv[2])
            dur = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
            pwm("forward", duty, dur)
        elif cmd in ("pwmrev",):
            duty = float(sys.argv[2])
            dur = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
            pwm("reverse", duty, dur)
        elif cmd in ("ramp",):
            start = float(sys.argv[2])
            end = float(sys.argv[3])
            dur = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
            ramp("forward", start, end, dur)
        elif cmd in ("ramprev",):
            start = float(sys.argv[2])
            end = float(sys.argv[3])
            dur = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
            ramp("reverse", start, end, dur)
        else:
            usage()
    except IndexError:
        print("Missing arguments")
        usage()
    except subprocess.CalledProcessError as e:
        print("gpioset failed:", e)
        stop()
    except KeyboardInterrupt:
        stop()
