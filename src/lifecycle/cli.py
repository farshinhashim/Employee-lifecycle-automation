import argparse
import json
import logging
import os
import sys

from lifecycle.config import Settings
from lifecycle.workflows import LifecycleWorkflow


def build_parser():
    parser = argparse.ArgumentParser(description="Mal employee lifecycle automation")
    sub = parser.add_subparsers(dest="command", required=True)
    onboard = sub.add_parser("onboard", help="Provision a new employee")
    onboard.add_argument("--first-name", required=True)
    onboard.add_argument("--last-name", required=True)
    onboard.add_argument("--email", required=True)
    onboard.add_argument("--password", required=True)
    offboard = sub.add_parser("offboard", help="Revoke a departing employee's access")
    offboard.add_argument("--email", required=True)
    offboard.add_argument("--confirm", action="store_true", help="Confirm destructive real-mode actions")
    return parser


def main(argv=None):
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = build_parser().parse_args(argv)
    settings = Settings()
    try:
        settings.validate_real()
        if settings.mode not in {"mock", "real"}:
            raise ValueError("INTEGRATION_MODE must be 'mock' or 'real'")
        if args.command == "offboard" and settings.mode == "real" and not settings.dry_run:
            if not args.confirm:
                raise ValueError("Real offboarding requires --confirm")
            if not sys.stdin.isatty():
                raise ValueError("Real offboarding requires an interactive terminal for target confirmation")
            typed = input(f"Type the exact departing email '{args.email}' to proceed: ")
            if typed != args.email:
                raise ValueError("Confirmation did not match; aborting")
        workflow = LifecycleWorkflow(settings)
        if args.command == "onboard":
            result = workflow.onboard(args.first_name, args.last_name, args.email, args.password)
        else:
            result = workflow.offboard(args.email)
        print(json.dumps(result, indent=2))
        return 1 if result["failures"] else 0
    except Exception as exc:
        logging.error("Workflow aborted: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
