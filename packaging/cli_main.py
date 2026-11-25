"""PyInstaller entry point for the standalone Metadata Studio CLI binary."""
import sys

from metadata_studio.cli import main

if __name__ == "__main__":
    sys.exit(main())
