from __future__ import annotations

import traceback

from app.logging.setup import configure_logging
from app.validation.startup import validate_runtime


def main() -> int:
    logger = configure_logging()
    runtime = validate_runtime(profile="desktop")
    if not runtime.ok:
        logger.error("Startup dependency validation failed: %s", runtime.errors)
        return 2

    try:
        from app.desktop.window import run_desktop

        return run_desktop()
    except Exception as exc:  # pragma: no cover
        logger.exception("Uncaught fatal error: %s", exc)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
