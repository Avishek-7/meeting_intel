"""Alembic migration helper.

Usage:
    python -m scripts.apply_migrations          # alembic upgrade head
    python -m scripts.apply_migrations --stamp  # alembic stamp head
"""

import argparse
import subprocess
import sys
import structlog

logger = structlog.get_logger("migrations")


def apply_migrations(stamp: bool = False) -> bool:
    """Apply Alembic migrations (or stamp existing schema as current)."""
    cmd = ["alembic", "stamp" if stamp else "upgrade", "head"]
    logger.info("Running Alembic", command=" ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Alembic command failed", returncode=exc.returncode)
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Apply Alembic migrations")
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Mark existing schema as current revision without running DDL",
    )
    args = parser.parse_args()
    success = apply_migrations(stamp=args.stamp)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
