"""Entry point: ``python -m water_quality <subcommand> ...``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
