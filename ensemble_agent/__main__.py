"""Entry point for python -m ensemble_agent."""

import asyncio
import sys

from .config import parse_args
from .agent import run_agent


def main():
    config = parse_args()
    try:
        asyncio.run(run_agent(config))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
