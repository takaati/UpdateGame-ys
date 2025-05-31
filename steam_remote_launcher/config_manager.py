import json
import logging

logger = logging.getLogger('SteamRemoteLauncher.ConfigManager')

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

def load_config(filepath="config.json"):
    """
    Loads, validates, and returns the configuration from a JSON file.
    """
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file '{filepath}' not found.")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in configuration file '{filepath}'.")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred while reading config file '{filepath}': {e}")
        return None

    # Validate remote_machines
    if not isinstance(config.get('remote_machines'), list):
        logger.error("'remote_machines' must be a list in the configuration.")
        return None

    expected_machine_keys = {
        "host": str,
        "port": int,
        "username": str,
        "ssh_key_path": (str, type(None)), # Allows string or null
        "os_type": str, # Added os_type
        "steam_exe_path": str,
        "steamcmd_exe_path": str
    }

    valid_os_types = ["linux", "windows"] # Optional: for stricter validation

    for i, machine in enumerate(config['remote_machines']):
        if not isinstance(machine, dict):
            logger.error(f"Item at index {i} in 'remote_machines' is not a valid object.")
            return None
        for key, expected_type in expected_machine_keys.items():
            if key not in machine:
                logger.error(f"Missing key '{key}' in remote_machines entry {i} for host '{machine.get('host', 'Unknown')}'.")
                return None
            
            current_value = machine[key]
            # Special handling for ssh_key_path allowing None (null in JSON)
            if key == "ssh_key_path" and current_value is None:
                is_correct_type = True # None is allowed
            elif isinstance(expected_type, tuple): # Handles cases like (str, type(None))
                is_correct_type = isinstance(current_value, expected_type)
            else: # Single type
                is_correct_type = isinstance(current_value, expected_type)

            if not is_correct_type:
                logger.error(f"Key '{key}' in remote_machines entry {i} for host '{machine.get('host', 'Unknown')}' has incorrect type. Expected {expected_type}, got {type(current_value)}.")
                return None
            
            # Validate os_type value
            if key == "os_type" and current_value not in valid_os_types:
                logger.warning(f"Key 'os_type' in remote_machines entry {i} for host '{machine.get('host', 'Unknown')}' has value '{current_value}'. Expected one of {valid_os_types}. Proceeding anyway.")
                # If strict validation is required:
                # logger.error(f"Key 'os_type' in remote_machines entry {i} for host '{machine.get('host', 'Unknown')}' must be one of {valid_os_types}, got '{current_value}'.")
                # return None

    # Validate game_app_ids
    game_app_ids = config.get('game_app_ids')
    if not isinstance(game_app_ids, list):
        logger.error("'game_app_ids' must be a list in the configuration.")
        return None
    if not all(isinstance(item, int) for item in game_app_ids):
        logger.error("All items in 'game_app_ids' must be integers.")
        return None

    logger.info(f"Configuration file '{filepath}' loaded and validated successfully.")
    return config
