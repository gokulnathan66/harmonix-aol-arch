"""
Test configuration for pytest
"""
import sys
import os

# Add parent directory to path so we can import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
