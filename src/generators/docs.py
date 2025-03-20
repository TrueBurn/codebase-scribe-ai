# This file has been deprecated and its functionality has been moved to other modules.
# It is kept as a placeholder to prevent import errors in case any external code still references it.
# The generate_readme functionality is now in src/generators/readme.py
# The generate_architecture functionality is now in src/generators/architecture.py

from pathlib import Path
from typing import Dict

def deprecated_function(*args, **kwargs):
    """Placeholder for deprecated functions."""
    raise DeprecationWarning(
        "This function has been deprecated. Please use the equivalent functionality "
        "from src/generators/readme.py or src/generators/architecture.py"
    )

# Deprecated functions - kept as references that raise warnings
async def generate_readme(*args, **kwargs):
    """
    Deprecated: Use src.generators.readme.generate_readme instead.
    """
    return deprecated_function(*args, **kwargs)

async def generate_architecture(*args, **kwargs):
    """
    Deprecated: Use src.generators.architecture.generate_architecture instead.
    """
    return deprecated_function(*args, **kwargs)

def _generate_tree_structure(*args, **kwargs):
    """
    Deprecated: Internal function no longer used.
    """
    return deprecated_function(*args, **kwargs)

def _generate_component_description(*args, **kwargs):
    """
    Deprecated: Internal function no longer used.
    """
    return deprecated_function(*args, **kwargs)