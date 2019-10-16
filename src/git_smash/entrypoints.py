import argparse
import logging
import sys

from .smash import Smash


def git_smash():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-l", "--loglevel", default="info", help="log level, default=info"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="automatically clean the backup smash branch",
    )
    parser.add_argument("--drop", action="append", help="drop the given branches")
    parser.add_argument("--push", action="store_true", help="push the result upstream")
    parser.add_argument(
        "--reset-base", action="store_true", help="reset the branch to the base branch"
    )
    parser.add_argument("action", help="the action to take")

    args, remainder = parser.parse_known_args()

    loglevel = getattr(logging, args.loglevel.upper())
    log_format = "%(levelname)s %(message)s"
    logging.basicConfig(level=loglevel, format=log_format)

    # drop sh logging
    logger = logging.getLogger("sh").setLevel(logging.WARNING)

    smash = Smash(clean_backups=args.clean, drop_branches=args.drop, push=args.push)

    fn = getattr(smash, args.action, None)
    if not fn:
        sys.exit(f"ERROR: action {args.action} not defined")

    sys.exit(fn(*remainder))
