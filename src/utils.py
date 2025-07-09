import random
import string
import json
import os
from typing import Any, Dict

def random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a JSON file. Returns an empty dict on error."""
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Config file {config_file} is corrupt. Using defaults.")
    except Exception:
        pass
    return {}

def save_config(config_file: str, config: Dict[str, Any]) -> None:
    """Save configuration to a JSON file. Logs error on failure."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}") 