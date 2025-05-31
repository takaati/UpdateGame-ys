from config_manager import load_config
from remote_operations import (
    connect_ssh,
    # execute_remote_command, # Not directly used in main flow now
    close_ssh_connection,
    ensure_steam_closed,
    launch_steam_client,
    update_game_with_steamcmd,
    shutdown_steam_client
)
import getpass
import os
import logging

# --- Logger Setup ---
logger = logging.getLogger('SteamRemoteLauncher')

def setup_logging():
    logger.setLevel(logging.INFO)
    
    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # File Handler
    # Ensure the directory for the log file exists or handle potential errors
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            # Fallback or print error if log directory creation fails
            print(f"Warning: Could not create log directory {log_dir}. File logging might fail. Error: {e}")
            # Potentially disable file handler here or log to current dir
    
    fh = logging.FileHandler(os.path.join(log_dir, "steam_launcher.log"))
    fh.setLevel(logging.INFO) # Or DEBUG for more verbosity in file
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    
    # Add Handlers
    if not logger.handlers: # Avoid adding multiple handlers if this function is called again
        logger.addHandler(ch)
        logger.addHandler(fh)

def main():
    setup_logging()

    # --- Configuration Loading ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, "config.json")
    logger.info(f"Attempting to load configuration from: {config_file_path}")
    config = load_config(config_file_path)

    if not config:
        logger.error("Failed to load configuration. Exiting.")
        return

    if not config.get('remote_machines'):
        logger.warning("No remote machines configured. Exiting.")
        return
        
    logger.info("Configuration loaded successfully.\n")

    # --- Prompt for Steam Credentials (or use hardcoded for CI/testing) ---
    logger.info("--- Steam Credentials ---")
    steam_username = ""
    steam_password = ""
    try:
        # Attempt interactive input first
        steam_username = input("Enter your Steam username: ")
        steam_password = getpass.getpass("Enter your Steam password: ")
        logger.info("Steam credentials obtained via interactive input.")
    except EOFError:
        logger.warning("EOFError encountered during interactive input. Falling back to hardcoded credentials for testing.")
        # Hardcoding for non-interactive environment testing:
        steam_username = "testuser_ci"
        steam_password = "testpassword_ci"
        logger.info(f"Steam username (hardcoded for testing): {steam_username}")
        logger.info("Steam password (hardcoded for testing): [hidden]")
    
    logger.info("Steam credentials obtained.\n")


    # --- Iterate Through Remote Machines ---
    for machine_config in config.get('remote_machines', []):
        host = machine_config.get('host')
        port = machine_config.get('port')
        ssh_username = machine_config.get('username')
        ssh_key_path = machine_config.get('ssh_key_path')
        steam_exe_path = machine_config.get('steam_exe_path')
        steamcmd_exe_path = machine_config.get('steamcmd_exe_path')
        os_type = machine_config.get('os_type')

        logger.info(f"--- Processing machine: {ssh_username}@{host} ---")

        if not all([host, port, ssh_username, steam_exe_path, steamcmd_exe_path, os_type]):
            logger.error(f"Machine {host} is missing one or more critical configuration fields. Skipping.")
            continue

        # --- SSH Connection ---
        logger.info(f"Attempting SSH connection to {ssh_username}@{host}:{port}...")
        ssh_client = connect_ssh(
            hostname=host,
            port=port,
            username=ssh_username,
            key_filepath=ssh_key_path
        )

        if not ssh_client:
            logger.error(f"Failed to connect to {host} via SSH. Skipping this machine.\n")
            continue
        
        logger.info(f"Successfully connected to {host} via SSH.")

        try:
            # --- Steam Client Operations ---
            logger.info(f"Attempting to ensure Steam client is closed on {host}...")
            if not ensure_steam_closed(ssh_client, steam_exe_path, os_type):
                logger.warning(f"Could not ensure Steam was closed on {host}, or command failed. Proceeding with caution.")

            logger.info(f"Attempting to launch Steam client on {host} for user {steam_username}...")
            if not launch_steam_client(ssh_client, steam_exe_path, steam_username, steam_password, os_type):
                logger.warning(f"Failed to launch Steam client on {host}. Further operations for this machine might fail.")
            else:
                logger.info(f"Steam client launch command issued on {host}.")

            # --- Placeholder for user interaction/Steam Guard ---
            logger.info(f"Steam launched on {host}. Waiting for user to handle Steam Guard if prompted and confirm readiness.")
            try:
                input("Press Enter in this console when ready to proceed with game updates and client shutdown...")
                logger.info("User confirmed readiness. Proceeding with game updates...")
            except EOFError:
                logger.warning("EOFError: No interactive user input for 'Press Enter'. Assuming readiness for automated testing flow.")


            # --- Game Updates via SteamCMD ---
            if config.get('game_app_ids'):
                if not steamcmd_exe_path:
                    logger.error(f"'steamcmd_exe_path' not configured for {host}. Skipping game updates.")
                else:
                    logger.info(f"--- Updating games on {host} ---")
                    for app_id in config['game_app_ids']:
                        logger.info(f"Attempting to update AppID {app_id} on {host}...")
                        # Adjust remote_temp_dir based on OS and user context if possible
                        win_temp_dir_guess = f"C:\\Users\\{ssh_username}\\AppData\\Local\\Temp"
                        temp_dir_for_os = "/tmp" if os_type == "linux" else win_temp_dir_guess
                        
                        update_success = update_game_with_steamcmd(
                            ssh_client=ssh_client,
                            steamcmd_exe_path=steamcmd_exe_path,
                            app_id=app_id,
                            steam_username=steam_username,
                            steam_password=steam_password,
                            os_type=os_type,
                            remote_temp_dir=temp_dir_for_os
                        )
                        if update_success:
                            logger.info(f"AppID {app_id} update reported success on {host}.")
                        else:
                            logger.warning(f"AppID {app_id} update reported failure or could not be confirmed on {host}.")
            else:
                logger.info("No 'game_app_ids' configured. Skipping game updates.")

            # --- Shutdown Steam Client ---
            logger.info(f"Attempting to shut down Steam client on {host}...")
            if not shutdown_steam_client(ssh_client, steam_exe_path, os_type):
                logger.warning(f"Failed to attempt Steam client shutdown on {host}.")
            else:
                logger.info(f"Steam client shutdown command issued on {host}.")

        except Exception as e:
            logger.exception(f"An unexpected error occurred while processing machine {host}: {e}")
        finally:
            # --- Close SSH Connection ---
            logger.info(f"Closing SSH connection to {host}...")
            close_ssh_connection(ssh_client)
            logger.info(f"--- Finished processing machine: {host} ---\n")

    logger.info("All configured machines processed. Exiting application.")

if __name__ == "__main__":
    main()
