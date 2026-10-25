"""Main CLI entrypoint for AI Email Classifier & WhatsApp Alerter."""

import argparse
import logging
import sys

from sorter.config import load_config
from sorter.service import EmailMonitorService
from sorter.storage import Storage


def setup_logging(verbose: bool = False) -> None:
    """Configure console logging level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Parse CLI arguments and dispatch service execution."""
    parser = argparse.ArgumentParser(
        description="AI Email Classifier & WhatsApp Alerter Daemon"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--once",
        action="store_true",
        help="Run a single polling cycle and exit",
    )
    group.add_argument(
        "--baseline",
        action="store_true",
        help="Initial sync: mark existing unread emails as processed without dispatching WhatsApp alerts",
    )
    group.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuous polling loop (default mode)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging output",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    try:
        config = load_config()
    except Exception as e:
        logger.error("Configuration error: %s", e)
        return 1

    storage = Storage(config.db_path)
    service = EmailMonitorService(config, storage)

    if args.baseline:
        logger.info("Running baseline sync (recording unread emails without alerting)...")
        service.run_once(alert_new=False)
        logger.info("Baseline sync completed.")
        return 0
    elif args.once:
        logger.info("Running single polling cycle...")
        alerts = service.run_once(alert_new=True)
        logger.info("Cycle completed. Dispatched %d alert(s).", alerts)
        return 0
    else:
        # Default or --daemon
        logger.info("Running in daemon mode...")
        service.start()
        return 0


if __name__ == "__main__":
    sys.exit(main())
