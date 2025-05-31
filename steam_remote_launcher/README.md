# Steam Remote Launcher

A Python application to remotely manage Steam clients on multiple machines. This tool allows users to automate the process of logging into Steam, updating specified games via SteamCMD, and then shutting down the Steam client. It's designed for users who manage Steam installations on several remote computers (e.g., for game servers, testing, or personal use across different OS environments).

## Features

*   **Remote Steam Client Management:** Launch and shut down the Steam client on configured remote machines.
*   **Automated Login:** Logs into the Steam client using provided credentials (entered at runtime, not stored in config).
*   **Game Updates via SteamCMD:** Automates updating specified game AppIDs using SteamCMD scripts.
*   **Cross-Platform Support (Conceptual):** Designed to work with both Linux and Windows remote machines (requires correct paths in config).
*   **SSH-Based Operations:** All remote operations are performed over SSH, leveraging Paramiko for connections.
*   **Configuration File:** Machine details and game AppIDs are managed via a `config.json` file.
*   **Logging:** Comprehensive logging to console and a file (`logs/steam_launcher.log`) for status tracking and troubleshooting.

## Prerequisites

### Control Machine (where this script runs)
*   Python 3.x (developed with 3.10+)
*   `paramiko` library: Install using `pip install paramiko`

### Remote Machines
*   **SSH Server:** An SSH server must be installed, configured, and running.
    *   For Windows, this could be OpenSSH Server for Windows.
    *   For Linux, `sshd` is commonly available.
*   **Steam Client:** The official Steam client must be installed.
*   **SteamCMD:** SteamCMD (the command-line version of Steam) must be installed and executable.
*   **Firewall:** The firewall on remote machines must be configured to allow incoming SSH connections on the specified port.

## Setup

1.  **Clone the Repository (or Download Files):**
    ```bash
    # If you have git installed
    # git clone <repository_url>
    # cd steam_remote_launcher
    ```
    Alternatively, download the `steam_remote_launcher` directory containing `main.py`, `remote_operations.py`, `config_manager.py`, and `config_example.json`.

2.  **Install Dependencies:**
    Open your terminal or command prompt and run:
    ```bash
    pip install paramiko
    ```

3.  **Configure `config.json`:**
    *   In the `steam_remote_launcher` directory, copy the example configuration file `config_example.json` to `config.json`.
    *   Open `config.json` with a text editor and modify it according to your setup.

    **Configuration Options:**

    *   `remote_machines` (list): An array of objects, where each object represents a remote machine to manage.
        *   `host` (string): The IP address or hostname of the remote machine (e.g., `"192.168.1.101"`).
        *   `port` (integer): The SSH port on the remote machine (e.g., `22`).
        *   `username` (string): The username for SSH authentication on the remote machine (e.g., `"steamuser"`).
        *   `ssh_key_path` (string or `null`):
            *   The absolute path to the SSH private key file for authentication (e.g., `"/home/user/.ssh/id_rsa"` or `"C:\\Users\\User\\.ssh\\id_rsa"`).
            *   Use `null` if you are using password-based SSH authentication (not recommended for security) or if your SSH key is managed by an SSH agent and doesn't require a specific path.
        *   `os_type` (string): The operating system of the remote machine. Must be either `"linux"` or `"windows"`. This is crucial as commands differ between OSes.
        *   `steam_exe_path` (string): The full, absolute path to the Steam executable.
            *   Example for Linux: `"/usr/bin/steam"` or `"/home/steamuser/Steam/steam.sh"`
            *   Example for Windows: `"C:\\Program Files (x86)\\Steam\\steam.exe"`
        *   `steamcmd_exe_path` (string): The full, absolute path to the SteamCMD executable.
            *   Example for Linux: `"/home/steamuser/steamcmd/steamcmd.sh"`
            *   Example for Windows: `"C:\\steamcmd\\steamcmd.exe"`
    *   `game_app_ids` (list): An array of integers, representing the Steam AppIDs of the games you want to update.
        *   Example: `[730, 440]` (CS2, TF2)
        *   You can find AppIDs for games on websites like [SteamDB](https://steamdb.info/).

4.  **SSH Key Authentication (Recommended):**
    *   For enhanced security, it's highly recommended to use SSH key-based authentication instead of passwords for connecting to your remote machines.
    *   This involves generating an SSH key pair on your control machine and copying the public key to the `authorized_keys` file on each remote machine.
    *   If your private key is passphrase-protected, ensure an SSH agent is managing it, or you might encounter issues if the script cannot interactively prompt for the passphrase.

## Usage

1.  **Navigate to the Directory:**
    Open your terminal or command prompt and change to the `steam_remote_launcher` directory.
    ```bash
    cd path/to/steam_remote_launcher
    ```

2.  **Run the Script:**
    Execute the main script using Python:
    ```bash
    python main.py
    ```

3.  **Enter Steam Credentials:**
    *   The script will first prompt you to enter your global Steam username.
    *   Then, it will prompt for your Steam password. The password input will be hidden (not echoed to the screen).
    *   **These credentials are used for logging into the Steam client and SteamCMD on the remote machines and are NOT stored in `config.json` or any other file by this script.**

4.  **Monitor Operations:**
    *   The script will iterate through each machine configured in `config.json`.
    *   It will print status messages to the console indicating the current operation (connecting, launching Steam, updating games, etc.).
    *   **Steam Guard Prompt:** When Steam is launched on a remote machine, especially for the first time or from a new location, Steam Guard (Steam's two-factor authentication) may be triggered. The script will pause with a message like:
        ```
        Steam launched on <host>. Please manually handle Steam Guard if prompted.
        Press Enter in this console when ready to proceed with game updates and client shutdown...
        ```
        During this pause, you may need to:
        *   Access the remote machine (e.g., via VNC, RDP, or physically) to see the Steam client interface.
        *   Enter the Steam Guard code sent to your email or generated by your mobile authenticator.
        *   Once the Steam client is fully logged in and operational on the remote machine, return to the console where `main.py` is running and press Enter to allow the script to proceed.

5.  **Logging:**
    *   All operations, informational messages, warnings, and errors are logged to both the console and a log file.
    *   The log file is located at `steam_remote_launcher/logs/steam_launcher.log`. This file is useful for troubleshooting any issues.

## How it Works

The application follows this general workflow:

1.  **Load Configuration:** Reads machine details and game AppIDs from `config.json`.
2.  **Get Steam Credentials:** Prompts the user for their Steam username and password at runtime.
3.  **Process Each Machine:** For every machine defined in the configuration:
    a.  **SSH Connection:** Establishes an SSH connection to the remote machine.
    b.  **Ensure Steam Closed (Optional):** Attempts to close any existing Steam processes to ensure a clean login.
    c.  **Launch Steam:** Launches the Steam client using the provided credentials.
    d.  **User Confirmation:** Pauses, allowing the user to handle Steam Guard or other manual interventions on the remote Steam client. The user presses Enter in the script's console to continue.
    e.  **Update Games (SteamCMD):** For each AppID in `game_app_ids`:
        i.  Generates a temporary SteamCMD script.
        ii. Uploads this script to the remote machine via SFTP.
        iii. Executes SteamCMD with the script to validate and update the game.
        iv. Deletes the temporary script from the remote machine.
    f.  **Shutdown Steam:** Sends a command to shut down the Steam client.
    g.  **Disconnect SSH:** Closes the SSH connection.

## Error Handling & Logging

*   The script provides feedback on its operations directly to the console.
*   Detailed logs, including errors and exceptions, are stored in `steam_remote_launcher/logs/steam_launcher.log`.
*   **Common Issues:**
    *   **SSH Connectivity:** Ensure the remote machine is reachable, the SSH server is running, and firewall rules are correct. Verify SSH username and port. If using key-based auth, ensure the key path is correct and the key is authorized on the server.
    *   **Incorrect Paths:** Double-check `steam_exe_path` and `steamcmd_exe_path` in `config.json`. These must be exact, full paths.
    *   **Steam Guard:** Be prepared to handle Steam Guard prompts, especially on initial runs.
    *   **Permissions:** The user under which Steam/SteamCMD runs on the remote machine needs appropriate permissions to write to game installation directories. SFTP operations also require correct permissions for the temporary script directory.

## Testing

*   **Start Small:** It's highly recommended to test the setup with a single, non-critical remote machine first to ensure your configuration and paths are correct.
*   **Manual SSH Check:** If you encounter connection issues, try connecting to the remote machine manually using a standard SSH client (like PuTTY, OpenSSH client from terminal) with the same credentials/key file specified in `config.json`. This can help diagnose SSH-specific problems.
*   **Dedicated Steam Account (Recommended):** For security and to avoid disrupting your primary Steam account, consider using a dedicated Steam account for this automation tool, especially if managing game servers or shared machines.
*   **Steam Guard Behavior:** Understand that initial logins to new machines will almost certainly trigger Steam Guard. The script is designed to pause for this manual intervention. Subsequent runs might not trigger it as often if Steam recognizes the "machine."

---
*This README provides guidance for using the Steam Remote Launcher. Ensure all paths and credentials are handled securely.*
