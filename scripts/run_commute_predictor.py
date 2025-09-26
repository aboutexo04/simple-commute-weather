#!/usr/bin/env python3
"""Command-line script for commute weather predictions."""

import sys
from pathlib import Path

# Add src to path so we can import our package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from commute_weather.main import main

if __name__ == "__main__":
    main()