"""Shortcut to run Phase 7 sanity suite."""

import asyncio
import sys
from tests.sandbox.sanity_suite import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
