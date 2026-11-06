"""Allows `python -m typerunner` as well as the installed `typerunner` command."""

import sys

from .game import main

if __name__ == "__main__":
    sys.exit(main())
