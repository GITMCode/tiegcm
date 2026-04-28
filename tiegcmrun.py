#!/usr/bin/env python3
"""Thin entry point for the TIEGCMrun tool.

Run from the repository root:
    python tiegcmrun.py [options]
"""
import os
import sys

# Add the tiegcmrun package directory to the module search path so that
# the internal imports (compile, misc, config, etc.) resolve correctly.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiegcmrun"))

from tiegcmrun import tiegcmrun

if __name__ == "__main__":
    tiegcmrun()
