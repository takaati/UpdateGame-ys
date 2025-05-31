import paramiko
import tempfile
import os
import logging
import socket # For socket.timeout in connect_ssh

logger = logging.getLogger('SteamRemoteLauncher.RemoteOps')

def connect_ssh(hostname, port, username, password=None, key_filepath=None):
    """
    Establishes an SSH connection to a remote machine.
    Returns the connected SSH client object or None.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"Attempting to connect to {username}@{hostname}:{port}...")
        if key_filepath:
            logger.info(f"Using SSH key: {key_filepath}")
            client.connect(hostname, port=port, username=username, key_filename=key_filepath, timeout=10)
        elif password:
            logger.info("Using password authentication.") # Password itself is not logged.
            client.connect(hostname, port=port, username=username, password=password, timeout=10)
        else:
            logger.info("Attempting connection with available SSH agent or default keys...")
            client.connect(hostname, port=port, username=username, timeout=10)
        
        logger.info(f"Successfully connected to {hostname}.")
        return client
    except paramiko.AuthenticationException as auth_err:
        logger.error(f"Authentication failed when connecting to {hostname}: {auth_err}")
    except paramiko.SSHException as ssh_err:
        logger.error(f"SSH error when connecting to {hostname}: {ssh_err}")
    except FileNotFoundError:
        logger.error(f"SSH key file not found at '{key_filepath}'.")
    except socket.timeout:
        logger.error(f"Connection timed out when connecting to {hostname}.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred when connecting to {hostname}.") # .exception automatically adds exc_info=True
    
    return None

def execute_remote_command(client, command):
    """
    Executes a command on the remote machine.
    Returns a tuple (stdout_str, stderr_str) or (None, None) on failure.
    """
    if not client:
        logger.error("SSH client is not connected. Cannot execute command.")
        return None, None

    try:
        logger.info(f"Executing remote command: {command}")
        stdin, stdout, stderr = client.exec_command(command, timeout=300) # 5 min timeout for commands
        
        stdout_str = stdout.read().decode('utf-8', errors='replace').strip()
        stderr_str = stderr.read().decode('utf-8', errors='replace').strip()
        exit_status = stdout.channel.recv_exit_status() # Get exit status

        if stdout_str:
            # For very verbose output, consider logging only a summary or if exit_status != 0
            logger.debug(f"Stdout from '{command}':\n{stdout_str}")
        if stderr_str:
            # Log stderr as warning, as some commands use it for non-fatal info
            logger.warning(f"Stderr from '{command}':\n{stderr_str}")
        
        if exit_status != 0:
            logger.error(f"Command '{command}' exited with status {exit_status}.")
            # Potentially return None, None here if any non-zero exit is critical error
            # For now, we return output as command might have partially succeeded or output is needed.

        return stdout_str, stderr_str
    except paramiko.SSHException as ssh_err:
        logger.error(f"Failed to execute command '{command}': {ssh_err}")
    except socket.timeout: # Timeout during command execution
        logger.error(f"Timeout during execution of command '{command}'.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during remote command execution '{command}': {e}")
        
    return None, None

def close_ssh_connection(client):
    """Closes the SSH connection."""
    if client:
        try:
            peername = client.get_transport().getpeername()[0] if client.get_transport() else "unknown host"
            logger.info(f"Closing SSH connection to {peername}.")
            client.close()
            logger.info("Connection closed.")
        except Exception as e:
            logger.exception(f"Error closing SSH connection: {e}")

def ensure_steam_closed(ssh_client, steam_exe_path, os_type):
    """Ensures any running Steam instance is closed on the remote machine."""
    if not ssh_client:
        logger.error("SSH client not connected for ensure_steam_closed.")
        return False

    logger.info(f"Attempting to ensure Steam is closed on remote machine ({os_type})...")
    command = None
    if os_type == 'linux':
        command = "pkill -f steam"
    elif os_type == 'windows':
        command = "taskkill /F /IM steam.exe /T"
    else:
        logger.error(f"Unsupported OS type '{os_type}' for closing Steam.")
        return False

    stdout, stderr = execute_remote_command(ssh_client, command)
    
    if stderr:
        ok_stderr_messages = ["no process found", "no tasks are running", "not found"]
        stderr_lower = stderr.lower()
        is_ok_stderr = any(msg in stderr_lower for msg in ok_stderr_messages)
        if not is_ok_stderr:
            logger.warning(f"Stderr while trying to close Steam (command: '{command}'): {stderr}")
        else:
            logger.info(f"Steam process not found or command indicated no running Steam (command: '{command}').")
    
    if stdout: # Usually no stdout for these commands on success
        logger.debug(f"Stdout while trying to close Steam (command: '{command}'): {stdout}")

    # Assuming command attempt is sufficient, actual success depends on OS & permissions
    # execute_remote_command logs errors if command itself fails to run
    return True


def launch_steam_client(ssh_client, steam_exe_path, steam_username, steam_password, os_type):
    """Launches the Steam client on the remote machine with login credentials."""
    if not ssh_client:
        logger.error("SSH client not connected for launch_steam_client.")
        return False

    logger.info(f"Attempting to launch Steam on remote machine ({os_type}) for user '{steam_username}'.")
    quoted_steam_exe_path = f'"{steam_exe_path}"'
    command = None

    if os_type == 'linux':
        command = f"DISPLAY=:0 {quoted_steam_exe_path} -login {steam_username} {steam_password} > /dev/null 2>&1 &"
    elif os_type == 'windows':
        command = f'START "" {quoted_steam_exe_path} -login {steam_username} {steam_password}'
    else:
        logger.error(f"Unsupported OS type '{os_type}' for launching Steam.")
        return False

    stdout, stderr = execute_remote_command(ssh_client, command) # stdout/stderr might be empty
    
    # For backgrounded GUI launch, success is hard to determine from output alone.
    # We log any output for debugging.
    if stdout:
        logger.debug(f"Stdout from Steam launch attempt: {stdout}")
    if stderr:
        logger.warning(f"Stderr from Steam launch attempt: {stderr}")
        
    logger.info(f"Steam launch command for '{steam_username}' attempted.")
    return True


def transfer_file_to_remote(ssh_client, local_path, remote_path):
    """Transfers a local file to the remote machine using SFTP."""
    if not ssh_client:
        logger.error("SSH client not connected for file transfer.")
        return False
    
    sftp = None
    try:
        sftp = ssh_client.open_sftp()
        logger.info(f"SFTP session opened. Transferring '{local_path}' to '{remote_path}'...")
        sftp.put(local_path, remote_path)
        logger.info(f"File '{local_path}' transferred successfully to '{remote_path}'.")
        return True
    except FileNotFoundError:
        logger.error(f"Local file '{local_path}' not found for SFTP transfer.")
    except IOError as e:
        logger.error(f"IOError during SFTP transfer of '{local_path}' to '{remote_path}': {e}")
    except paramiko.SFTPError as sftp_err:
        logger.error(f"SFTP error during transfer of '{local_path}' to '{remote_path}': {sftp_err}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during SFTP transfer of '{local_path}' to '{remote_path}': {e}")
    finally:
        if sftp:
            sftp.close()
            logger.debug("SFTP session closed.")
    return False

def delete_remote_file(ssh_client, remote_path):
    """Deletes a file on the remote machine using SFTP."""
    if not ssh_client:
        logger.error("SSH client not connected for remote file deletion.")
        return False

    sftp = None
    try:
        sftp = ssh_client.open_sftp()
        logger.info(f"SFTP session opened. Deleting remote file '{remote_path}'...")
        sftp.remove(remote_path)
        logger.info(f"Remote file '{remote_path}' deleted successfully.")
        return True
    except FileNotFoundError:
        logger.warning(f"Remote file '{remote_path}' not found for deletion (or already deleted).")
        # This might not be an error condition depending on desired behavior (idempotency)
        return True # Consider it success if file is already gone
    except IOError as e:
        logger.error(f"IOError during remote file deletion of '{remote_path}': {e}")
    except paramiko.SFTPError as sftp_err:
        logger.error(f"SFTP error during remote file deletion of '{remote_path}': {sftp_err}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during remote file deletion of '{remote_path}': {e}")
    finally:
        if sftp:
            sftp.close()
            logger.debug("SFTP session closed.")
    return False


def update_game_with_steamcmd(ssh_client, steamcmd_exe_path, app_id, 
                              steam_username, steam_password, os_type, remote_temp_dir="/tmp"):
    """Updates a game on the remote machine using a SteamCMD script."""
    if not ssh_client:
        logger.error("SSH client not connected for SteamCMD operation.")
        return False

    script_content = f"""
@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
login {steam_username} {steam_password}
app_update {app_id} validate
quit
""".strip()

    local_script_file = None
    # remote_script_path must be defined outside try for finally block, initialized to None
    remote_script_path_final = None 

    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", prefix="steamcmd_") as tmp_file:
            tmp_file.write(script_content)
            local_script_file = tmp_file.name
        logger.info(f"Generated local SteamCMD script: {local_script_file}")

        remote_script_filename = f"steamcmd_update_script_{app_id}.txt"
        if os_type == 'windows':
            win_temp_dir = remote_temp_dir.replace('/', '\\')
            remote_script_path_final = f"{win_temp_dir}\\{remote_script_filename}"
        else:
            remote_script_path_final = f"{remote_temp_dir}/{remote_script_filename}"
        
        logger.info(f"Attempting to transfer script to remote path: {remote_script_path_final}")
        if not transfer_file_to_remote(ssh_client, local_script_file, remote_script_path_final):
            logger.error("Failed to transfer SteamCMD script to remote machine.")
            return False # transfer_file_to_remote already logs details
        
        quoted_steamcmd_path = f'"{steamcmd_exe_path}"'
        quoted_remote_script_path = f'"{remote_script_path_final}"'
        
        steamcmd_command = ""
        if os_type == 'linux':
            steamcmd_command = f"{quoted_steamcmd_path} +runscript {quoted_remote_script_path}"
        elif os_type == 'windows':
            steamcmd_command = f"cmd /c {quoted_steamcmd_path} +runscript {quoted_remote_script_path}"
        else:
            logger.error(f"Unsupported OS type '{os_type}' for SteamCMD.")
            return False # Should not happen if config validation is good

        logger.info(f"Executing SteamCMD command: {steamcmd_command}")
        stdout, stderr = execute_remote_command(ssh_client, steamcmd_command)

        update_successful = False
        if stdout:
            logger.debug(f"SteamCMD Stdout for app '{app_id}':\n{stdout}")
            success_indicators = [
                f"Success! App '{app_id}' fully installed.",
                f"Success! App '{app_id}' already up to date."
            ]
            for indicator in success_indicators:
                if indicator in stdout:
                    logger.info(f"Detected SteamCMD success for app '{app_id}': {indicator}")
                    update_successful = True
                    break
            if not update_successful:
                logger.warning(f"SteamCMD success string not found in stdout for app '{app_id}'.")
        else:
            logger.warning(f"SteamCMD produced no stdout for app '{app_id}'.")

        if stderr: # Stderr from SteamCMD is usually important
            logger.error(f"SteamCMD Stderr for app '{app_id}':\n{stderr}")
            # Consider update_successful = False here if any stderr is a failure.
            # For now, only stdout indicates success.

        return update_successful

    except Exception as e:
        logger.exception(f"An error occurred during SteamCMD game update for app '{app_id}': {e}")
        return False
    finally:
        if local_script_file and os.path.exists(local_script_file):
            try:
                os.remove(local_script_file)
                logger.info(f"Cleaned up local script file: {local_script_file}")
            except OSError as e:
                logger.error(f"Error cleaning up local script file {local_script_file}: {e}")
        
        if ssh_client and remote_script_path_final:
            logger.info(f"Attempting to delete remote script file: {remote_script_path_final}")
            if not delete_remote_file(ssh_client, remote_script_path_final):
                logger.warning(f"Failed to delete remote script file '{remote_script_path_final}'. Manual cleanup may be needed.")
            # delete_remote_file logs its own success/failure.

def shutdown_steam_client(ssh_client, steam_exe_path, os_type):
    """Shuts down the Steam client on the remote machine."""
    if not ssh_client:
        logger.error("SSH client not connected for shutdown_steam_client.")
        return False

    logger.info(f"Attempting to shut down Steam on remote machine ({os_type})...")
    quoted_steam_exe_path = f'"{steam_exe_path}"'
    command = f"{quoted_steam_exe_path} -shutdown"

    stdout, stderr = execute_remote_command(ssh_client, command)

    if stdout: # Steam -shutdown might not produce much stdout
        logger.debug(f"Stdout from Steam shutdown attempt: {stdout}")
    if stderr: # Stderr might indicate it wasn't running or other issues
        logger.warning(f"Stderr from Steam shutdown attempt: {stderr}")
        
    logger.info(f"Steam shutdown command attempted via '{command}'.")
    # Success of -shutdown is hard to verify remotely without more complex process checks.
    # We assume the command attempt is sufficient if execute_remote_command didn't error out.
    return True
