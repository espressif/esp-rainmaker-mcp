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
*   `get_node_details(node_id: str = None)`:
    *   Get detailed information for nodes including config, status, and params.
    *   If `node_id` is provided, gets details for that specific node.
    *   If `node_id` is None, gets details for all nodes.
*   `get_node_status(node_id: str)`:
    *   Get the online/offline connectivity status for a specific node ID. Returns a dictionary.

### Device Control

*   `get_params(node_id: str)`:
    *   Get the current parameters (state, e.g., Power, Brightness) for a specific node ID. Returns a dictionary.
*   `set_params(node_id: str, params_dict: dict)`:
    *   Set parameters for one or more nodes using a JSON object (dictionary).
    *   **node_id**: Single node ID or comma-separated list of node IDs (e.g., `"node1"` or `"node1,node2,node3"`)
    *   **Multi-node support**: When multiple node IDs are provided, the same parameters will be applied to all specified nodes.
    *   Example: `{'Thermostat': {'Power': False}}` to turn off a thermostat.
    *   Bulk example: `set_params("light1,light2,light3", {'Light': {'Power': True}})` to turn on multiple lights.

### Schedule Management

*   `get_schedules(node_id: str)`:
    *   Get schedule information for a specific node.
    *   Returns the schedules configured for the node if any exist, along with support status.
*   `set_schedule(node_id: str, operation: str, ...)`:
    *   Manage schedules for one or more nodes. Supports add, edit, remove, enable, disable operations.
    *   **Parameters:**
        *   `node_id`: Single node ID or comma-separated list of node IDs (e.g., `"node1"` or `"node1,node2,node3"`)
        *   `operation`: Operation to perform (`add`, `edit`, `remove`, `enable`, `disable`)
        *   `schedule_id`: Schedule ID (required for edit, remove, enable, disable operations)
        *   `name`: Schedule name (required for add operation, optional for edit)
        *   `trigger`: Dictionary defining the trigger configuration (required for add, optional for edit)
        *   `action`: Dictionary defining the action configuration (required for add, optional for edit)
        *   `info`: Additional information for the schedule (optional)
        *   `flags`: General purpose flags for the schedule (optional)
    *   **Multi-node support**:
        *   For `add` operations: Creates the same schedule on all specified nodes with a common schedule ID
        *   For `edit/remove/enable/disable` operations: Applies the operation to the specified schedule on all nodes
        *   This is useful for bulk schedule management across multiple devices
    *   **Example trigger:** `{"m": 1110, "d": 31}` for 6:30 PM on weekdays
    *   **Example action:** `{"Light": {"Power": true}}` to turn on a light
    *   **Bulk example:** `set_schedule("light1,light2,light3", "add", name="Morning Lights", trigger={"m": 480, "d": 127}, action={"Light": {"Power": true}})` to add the same schedule to multiple lights

### Group Management (Home/Room Hierarchy)

ESP RainMaker supports organizing devices into groups with a home/room hierarchy. This enables logical organization and bulk operations on related devices.

*   `create_group(name: str, group_type: str = None, ...)`:
    *   Create a new group (home, room, or custom group).
    *   **Parameters:**
        *   `name`: Name of the group (required)
        *   `group_type`: Type of group ('home', 'room', or custom type)
        *   `description`: Description of the group (optional)
        *   `mutually_exclusive`: Set mutually exclusive flag (recommended for homes and rooms)
        *   `parent_group_id`: Parent group ID (required for rooms under a home)
        *   `nodes`: Comma-separated list of node IDs to add to the group (optional)
        *   `custom_data`: Custom data as JSON string (optional)
    *   **Examples:**
        *   Create home: `create_group("My Home", "home", mutually_exclusive=True)`
        *   Create room: `create_group("Living Room", "room", mutually_exclusive=True, parent_group_id="home_id")`

*   `get_group_details(group_id: str = None, include_nodes: bool = False)`:
    *   Get comprehensive group information.
    *   **Parameters:**
        *   `group_id`: ID of specific group to show (optional - if None, lists all groups)
        *   `include_nodes`: Include detailed node information for groups
    *   **When group_id is None:** Lists all groups with hierarchy
    *   **When group_id is provided:** Shows detailed information for that specific group
    *   **When include_nodes is True:** Includes comprehensive node details within groups

*   `update_group(group_id: str, name: str = None, ...)`:
    *   Edit an existing group's properties and manage nodes.
    *   **Hierarchical Node Addition**: When adding nodes to a subgroup (room), the function automatically:
        *   1. First adds the node to the parent group (e.g., "My Home")
        *   2. Then adds the node to the target subgroup (e.g., "Kitchen")
    *   **Parameters:**
        *   `group_id`: ID of the group to edit (required)
        *   `name`: New name for the group (optional)
        *   `description`: New description for the group (optional)
        *   `custom_data`: New custom data as JSON string (optional)
        *   `add_nodes`: Comma-separated list of node IDs to add to the group (optional)
        *   `remove_nodes`: Comma-separated list of node IDs to remove from the group (optional)
    *   **Examples:**
        *   Rename group: `update_group("group_id", name="New Name")`
        *   Add devices: `update_group("group_id", add_nodes="light1,light2")`
        *   Remove devices: `update_group("group_id", remove_nodes="switch1")`

*   `add_device_to_room(device_node_id: str, room_group_id: str)`:
    *   **Convenience function** for adding a device to a room with automatic parent group handling.
    *   **Hierarchical Behavior**: Automatically handles the ESP RainMaker requirement:
        *   1. First adds the device to the parent group (e.g., "My Home")
        *   2. Then adds the device to the target room group (e.g., "Kitchen")
    *   **Parameters:**
        *   `device_node_id`: The node ID of the device to add (required)
        *   `room_group_id`: The group ID of the room to add the device to (required)
    *   **Example:** `add_device_to_room("light1", "kitchen_group_id")`

#### Typical Group Workflow

1.  **Create a home:** `create_group("My Home", "home", mutually_exclusive=True)`
2.  **Create rooms:** `create_group("Living Room", "room", mutually_exclusive=True, parent_group_id="home_id")`
3.  **Add devices to rooms:** Choose one of these approaches:
    *   **Recommended:** `add_device_to_room("light1", "living_room_id")` (handles hierarchy automatically)
    *   **Alternative:** `update_group("living_room_id", add_nodes="light1,light2,switch1")` (also handles hierarchy automatically)
4.  **View hierarchy:** `get_group_details(include_nodes=True)`
5.  **Control room devices:** Use existing `set_params` and `set_schedule` with comma-separated node IDs from the room

> [!NOTE]
> **Hierarchical Group Management**: ESP RainMaker requires devices to be added to parent groups before subgroups.
> Both `update_group` and `add_device_to_room` automatically handle this hierarchy, ensuring devices are first added
> to the parent group (e.g., "My Home") and then to the target subgroup (e.g., "Kitchen").


## Typical Workflow

1.  Ensure you have logged in via `esp-rainmaker-cli login` in your terminal.
2.  Start your MCP client configured with this server.
3.  Use the `check_login_status` tool in the MCP client to verify the connection.
4.  Use tools like `get_nodes`, `get_params`, and `set_params` to interact with your devices.

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
