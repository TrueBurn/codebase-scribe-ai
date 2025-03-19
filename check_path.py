import sys
import os

print("Python Path:")
for path in sys.path:
    print(f"  - {path}")

print("\nCurrent Working Directory:")
print(f"  {os.getcwd()}")

print("\nTrying to import config module:")
try:
    from src.utils.config import ConfigManager, ConfigValidationError
    print("  Success! Module imported correctly.")
    print(f"  Module path: {ConfigManager.__module__}")
except ImportError as e:
    print(f"  Error: {e}")