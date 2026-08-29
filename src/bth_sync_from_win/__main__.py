import sys

from . import ui
from .cli import main


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        ui.warning("Interrupted.")
        sys.exit(130)
