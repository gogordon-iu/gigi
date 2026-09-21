"""
Main Command Line Interface for Gigi Social Robot.

Commands:
    gigi start        Start the background daemon (Bluetooth + TCP server)
    gigi verify       Run hardware and cognitive subsystem tests
    gigi calibrate    Run interactive motor calibration wizard
    gigi demo         Run demonstration of robot capabilities
    gigi web          Start the web-based Activity Planner
"""

import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gigi.cli")


def cmd_start(args):
    print("Starting Gigi Robot Service...")
    from gigi.core.daemon import main as daemon_main
    daemon_main()


def cmd_verify(args):
    from gigi.verification.cli import run_verification
    targets = args.subsystem if args.subsystem else ["all"]
    success = run_verification(targets)
    sys.exit(0 if success else 1)


def cmd_calibrate(args):
    from gigi.verification.hardware.calibrate_motors import main as calibrate_main
    calibrate_main()


def cmd_web(args):
    print(f"Starting Gigi Web Activity Planner on port {args.port}...")
    from gigi.interaction.web.app import app
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_demo(args):
    print("Running Gigi Capabilities Demo...")
    from gigi.core.robot import GigiRobot
    robot = GigiRobot(character_name="fuzzy", wakeup=True, activity="Demo")
    robot.run_character(
        viseme_data={"text": "Hello! I am Gigi the social robot.", "file": None},
        movement_data="wave_hello",
    )


def main():
    parser = argparse.ArgumentParser(description="Gigi Robot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start
    parser_start = subparsers.add_parser("start", help="Start Gigi background daemon")
    parser_start.set_defaults(func=cmd_start)

    # verify
    parser_verify = subparsers.add_parser("verify", help="Verify hardware and AI subsystems")
    parser_verify.add_argument("subsystem", nargs="*", default=["all"], help="Subsystems to verify")
    parser_verify.set_defaults(func=cmd_verify)

    # calibrate
    parser_calib = subparsers.add_parser("calibrate", help="Calibrate robot motors")
    parser_calib.set_defaults(func=cmd_calibrate)

    # web
    parser_web = subparsers.add_parser("web", help="Start web activity planner")
    parser_web.add_argument("--host", default="0.0.0.0", help="Host address")
    parser_web.add_argument("--port", type=int, default=5000, help="Port number")
    parser_web.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser_web.set_defaults(func=cmd_web)

    # demo
    parser_demo = subparsers.add_parser("demo", help="Run demonstration")
    parser_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
