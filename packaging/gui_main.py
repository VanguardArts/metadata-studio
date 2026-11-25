"""PyInstaller entry point for the standalone Metadata Studio GUI binary."""
import sys

from metadata_studio.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
