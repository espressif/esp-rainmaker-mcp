# ESP RainMaker MCP Server

This project provides a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server wrapper around the [`esp-rainmaker-cli`](https://github.com/espressif/esp-rainmaker-cli) Python library.
It allows MCP-compatible clients (like LLMs or applications such as Cursor, Claude Desktop, and Windsurf) to interact with your [ESP RainMaker](https://rainmaker.espressif.com/) devices using the official CLI.

## Introduction to Model Context Protocol (MCP)

The **Model Context Protocol (MCP)** is a standardized framework that enables AI systems to interact with external tools, data sources, and services in a unified manner. Introduced by Anthropic and adopted by major AI organizations, MCP acts as a universal interface, much like USB-C for hardware, allowing seamless integration across different platforms.

### Key Benefits of MCP in ESP RainMaker

- **Unified Interaction**: MCP allows AI models to access and control IoT devices using natural language prompts, making interactions more intuitive and accessible.
- **Real-time Control**: With MCP, users can execute actions such as turning devices on/off, adjusting settings, and managing schedules directly through AI interfaces.
- **Local Server, Cloud-Backed Control**: The ESP RainMaker MCP server runs locally and stores credentials on your machine. However, device management actions are performed via the official ESP RainMaker cloud APIs through the esp-rainmaker-cli.

By integrating MCP, the ESP RainMaker platform enhances its capabilities, allowing tools like Claude, Cursor, Windsurf, and Gemini CLI to manage IoT devices efficiently and securely.

## Prerequisites

*   **Python:** Version 3.10 or higher
*   **uv:** The `uv` Python package manager. Install from [Astral's uv documentation](https://docs.astral.sh/uv/getting-started/installation/).
*   **ESP RainMaker CLI Login:** You *must* have successfully logged into ESP RainMaker using the standard `esp-rainmaker-cli login` command in your terminal at least once. This server relies on the credentials saved by that process.
*   **RainMaker Nodes** added into your account since onboarding isn't supported by the MCP server.

## Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/espressif/esp-rainmaker-mcp.git
    cd esp-rainmaker-mcp
    ```

2.  **Install Dependencies using uv:**
    This command installs `esp-rainmaker-cli`, `mcp[cli]`, and any other dependencies listed in `pyproject.toml` into a virtual environment managed by `uv`.

    ```bash
    uv sync
    ```
    *(This assumes `uv` is installed)*

3. **Login to ESP Rainmaker using `esp-rainmaker-cli`**
    ```bash
    uv run esp-rainmaker-cli login
    ```

> [!NOTE]
> Direct login via username/password within MCP is not supported for security reasons. Please use the standard CLI login flow first.


## Client Configuration

To add this project as an MCP server in supported MCP clients (Cursor, Claude Desktop, Windsurf, and Gemini CLI), you'll need to add the same JSON configuration to each client's config file. The configuration is identical across all clients:

### MCP Server Configuration (All Clients)

Use the following JSON configuration for all MCP clients:

```json
{
   "mcpServers": {
      "ESP-RainMaker-MCP": {
         "command": "uv",
         "args": [
            "run",
            "--with",
            "esp-rainmaker-cli",
            "--with",
            "mcp[cli]",
            "mcp",
            "run",
            "<absolute_path_to_repo>/server.py"
         ]
      }
   }
}
```

> [!IMPORTANT]
> Replace `<absolute_path_to_repo>/server.py` with the actual **absolute path** to the `server.py` file within the cloned `esp-rainmaker-mcp` directory on your system.

### Cursor MCP Server Setup

1. Open Cursor and click on the settings (gear icon) at the top right.

2. Navigate to "Tools & Integrations" from the settings menu.

3. Click on "MCP Tools" in the integrations section.

4. Click on "New MCP Server" to add a new server.

5. This will open the mcp.json file. Add the JSON configuration shown above.

### Claude Desktop MCP Server Setup

1. Open Claude Desktop and go to Settings -> Developer -> Edit Config.

2. This will open the configuration file (claude_desktop_config.json). Add the JSON configuration shown above.

3. Save the changes and restart Claude Desktop to apply the new settings.

### Windsurf MCP Server Setup

1. Open Windsurf and look for the hammer-type icon under the chat text input area.

2. Click on the hammer icon and select "Configure" from the options. This will open the plugins window.

3. Click on "View raw config" which will show you the `~/.codium/windsurf/mcp_config.json` file.

4. Add the JSON configuration shown above to the file.

5. Save the changes and click on "Refresh" under the chat text window to load the ESP RainMaker MCP tools.

### Gemini CLI MCP Server Setup

1. Locate your Gemini CLI settings file. On macOS, this is typically at `~/.gemini/settings.json`.
2. Open the `settings.json` file in your preferred text editor.
3. Add the JSON configuration shown above to the `mcpServers` section of the file. If the section does not exist, create it as shown in the example.
4. Save the file and restart Gemini CLI if it is running.

> [!NOTE]
> The configuration for all four applications (Cursor, Claude Desktop, Windsurf, and Gemini CLI) is the same, so you can use the same JSON structure for all of them.

> [!NOTE]
> The `--with` arguments ensure `uv` includes the necessary dependencies when running the `mcp run` command.

## How it Works

This server acts as a bridge. It uses the `mcp` library to handle the Model Context Protocol communication. When a tool is called:

1.  It uses functions from the installed `esp-rainmaker-cli` library.
2.  The library functions read locally stored authentication tokens.
3.  It makes the necessary API calls to the ESP RainMaker cloud.
4.  It returns the results (or errors) back through the MCP protocol.


## Available Tools

This MCP server exposes the following tools for interacting with ESP RainMaker:

### Authentication & Configuration

*   `login_instructions()`:
    *   Provides instructions (formatted with Markdown) on how to log in using the standard `esp-rainmaker-cli login` command in your terminal.
        This server relies on the external CLI's browser-based login flow to securely store credentials.
        Rendering as Markdown depends on the MCP client's capabilities.
*   `check_login_status()`:
    *   Checks if a valid login session exists based on credentials stored locally by `esp-rainmaker-cli`.
        Confirms if the server can communicate with the ESP RainMaker backend.

### Node Management

*   `get_nodes()`:
    *   Lists all node IDs associated with the logged-in user.
*   `get_node_details(node_id: str = None, fields: str = None, name: str = None, type_: str = None)`:
    *   Get detailed information for nodes including config, status, and params.
    *   Supports filtering and field selection:
        - `fields`: comma-separated list of fields to include (e.g. "node_id,name,type,config,params,status.connectivity,fw_version,mapping_timestamp")
        - `name`: substring match (user-visible name from params)
        - `type_`: substring match (device type)
        - `node_id`: single node ID (for one node) or None (for all)
    *   Returns a dict (single node) or list of dicts (all nodes).
    *   Example:
        ```python
        get_node_details(ctx, fields="node_id,name,type")
        ```
*   `get_node_status(node_id: str)`:
    *   Get the online/offline connectivity status for a specific node ID.
*   `get_params(node_id: str)`:
    *   Get current parameter values for a device.
*   `set_params(node_id: str, params_dict: dict)`:
    *   Set parameters for one or more devices.
    *   `node_id`: Single ID or comma-separated list (e.g., "light1,light2")
    *   `params_dict`: Parameters to set, e.g., `{"Light": {"Power": true}}`

### Schedule Management

*   `get_schedules(node_id: str)`:
    *   Get schedules for a device.
*   `set_schedule(node_id: str, operation: str, ...)`:
    *   Manage device schedules.
    *   `operation`: "add", "edit", "remove", "enable", or "disable"
    *   For add/edit: Provide `name`, `trigger`, and `action`
    *   Common triggers:
        *   Daily 8 AM: `{"m": 480, "d": 127}`
        *   Weekdays 6:30 PM: `{"m": 1110, "d": 31}`
    *   Example action: `{"Light": {"Power": true}}`

### Group Management (Home/Room Hierarchy)

*   `create_group(name: str, group_type: str = None, ...)`:
    *   Create a home or room.
    *   Required: `name`, `group_type` ("home" or "room")
    *   For rooms: `parent_group_id` required
    *   Example: `create_group("Living Room", "room", parent_group_id="home_id")`

*   `get_group_details(group_id: str = None, include_nodes: bool = False)`:
    *   Get group information. For all groups, use `group_id=None`.
    *   Set `include_nodes=True` to include device details.
    *   Returns: Group hierarchy, members, and metadata.

*   `update_group(group_id: str, ...)`:
    *   Update group properties or manage devices.
    *   Optional: `name`, `description`, `add_nodes`, `remove_nodes`
    *   Examples:
        *   Rename: `update_group("group_id", name="New Name")`
        *   Add devices: `update_group("group_id", add_nodes="light1,light2")`

*   `add_device_to_room(device_node_id: str, room_group_id: str)`:
    *   Add device to room (handles parent group automatically).
    *   Example: `add_device_to_room("light1", "kitchen_id")`

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
