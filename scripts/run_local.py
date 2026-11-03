#!/usr/bin/env python3
"""Convenient local development runner for Prime Scalpers Bot."""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import main

if __name__ == "__main__":
    print("Starting Prime Scalpers Local Runner...")
    main()
