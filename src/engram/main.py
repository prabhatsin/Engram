# CLI entry point

import sys
from . import loop

if __name__ == "__main__":
    print(loop.run_agent(" ".join(sys.argv[1:])))