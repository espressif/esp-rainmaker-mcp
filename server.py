import asyncio
import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# MCP Imports
from mcp.server.fastmcp import FastMCP, Context

# ESP Rainmaker CLI Library Imports
from rmaker_lib import session as rainmaker_session
from rmaker_lib import node as rainmaker_node
from rmaker_lib import configmanager as rainmaker_config
from rmaker_lib.schedule_utils import format_schedule_params, extract_schedules_from_node_details

# Exceptions
from rmaker_lib.exceptions import (
    HttpErrorResponse,
    NetworkError,
    InvalidConfigError,
    InvalidUserError,
    ExpiredSessionError,
    AuthenticationError,
    InvalidJSONError,
    SSLError,
    RequestTimeoutError,
)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


# --- Lifespan Management ---
@asynccontextmanager
async def rainmaker_lifespan(server: FastMCP) -> AsyncIterator[None]:
    log.info("Starting ESP RainMaker MCP Server...")
    try:
        config = rainmaker_config.Config()
        log.info(f"RainMaker config directory: {rainmaker_config.RM_USER_CONFIG_DIR_VALUE}")
        log.info(f"RainMaker config file: {rainmaker_config.CONFIG_FILE}")
        log.info(f"Using RainMaker region: {config.get_region()}")
    except Exception as e:
        log.warning(f"Initial config check failed: {e}")
    yield None
    log.info("ESP RainMaker MCP Server shutting down.")


# --- Initialize MCP Server ---
mcp = FastMCP("ESP-RainMaker-MCP", lifespan=rainmaker_lifespan, dependencies=["esp-rainmaker-cli"])


# --- Helper Function to Check Login State ---
async def ensure_login_session() -> rainmaker_session.Session:
    """
    Attempts to initialize a RainMaker session using stored credentials.
    Raises exceptions if not logged in or session cannot be refreshed.
    """
    try:
        # Creating a Session object implicitly uses configmanager to get/refresh tokens
        # Use asyncio.to_thread as Session init can involve network calls for token refresh
        s = await asyncio.to_thread(rainmaker_session.Session)
        log.info("RainMaker session initialized successfully.")
        return s
    except (InvalidUserError, ExpiredSessionError, InvalidConfigError) as e:
        log.warning(f"Login check failed: {type(e).__name__} - {e}")
        raise ValueError(
            "Login required. Please run the 'login_instructions' tool for steps on how to log in using the standard RainMaker CLI, then use 'check_login_status'."
        ) from e
    except (NetworkError, SSLError, RequestTimeoutError) as e:
        log.error(f"Network/SSL error during session init: {e}")
        raise ConnectionError(f"Failed to connect to RainMaker API: {e}") from e
    except Exception as e:
        log.exception("Unexpected error during session initialization.")
        raise RuntimeError(f"An unexpected error occurred during login check: {e}") from e


# --- Tools Implementation ---


@mcp.tool()
async def login_instructions() -> str:
    """
    Provides instructions (formatted with Markdown) on how to log in
    using the standard ESP RainMaker CLI.
    This server relies on credentials saved locally by that process.
    Rendering as Markdown depends on the MCP client capabilities.
    """
    log.info("Providing login instructions (with Markdown).")
    try:
        # Run synchronous config calls in a thread
        # Using await asyncio.to_thread ensures we don't block the event loop
        config = await asyncio.to_thread(rainmaker_config.Config)
        login_url_base = await asyncio.to_thread(config.get_login_url)
        config_file_path = rainmaker_config.CONFIG_FILE
    except Exception as e:
        log.error(f"Error getting config for login instructions: {e}")
        # Provide placeholders if config loading fails
        login_url_base = "[Could not determine login URL]"
        config_file_path = "[Could not determine config path]"

    # Construct the message using Markdown syntax
    # Use f-string for cleaner variable insertion
    return f"""## ESP RainMaker Login Instructions

This MCP server uses the secure browser-based login flow provided by the official `esp-rainmaker-cli`.
Because this involves opening your browser and requires a temporary local webserver for the redirect, **it must be initiated from your own terminal**, not directly from this server.

**Steps:**

1.  Open a terminal or command prompt on your computer and navigate to `esp-rainmaker-mcp`.
2.  Run the command: `uv run esp-rainmaker-cli login`
3.  Your web browser should open automatically to the ESP RainMaker login page (URL starts with: `{login_url_base}`).
4.  Log in with your credentials (or sign up if needed).
5.  After successful login in the browser, you should see a "Login successful" message in your terminal.
6.  The CLI saves your session credentials locally (typically in `{config_file_path}`).
7.  Come back here and run the `check_login_status` tool to confirm the session is active for this server.
"""


@mcp.tool()
async def check_login_status(ctx: Context) -> str:
    """Checks if a valid login session exists based on stored credentials."""
    log.info("Checking login status.")
    try:
        # Attempt to create a session using stored credentials
        s = await ensure_login_session()
        # If session creation succeeded, try to get username for confirmation
        try:
            config = await asyncio.to_thread(rainmaker_config.Config)
            user_name = await asyncio.to_thread(config.get_user_name)
            log.info(f"Login status check successful for user: {user_name}")
            return f"Login session is active for user: {user_name}"
        except Exception as e_inner:
            # Handle cases where session is technically valid but getting username fails
            log.warning(f"Session check passed but error getting username: {e_inner}")
            return f"Login session seems active, but could not retrieve username. Try other commands. Error: {e_inner}"

    except ValueError as e:  # From ensure_login_session if not logged in
        return str(e)
    except ConnectionError as e:  # From ensure_login_session
        return f"Connection Error: {e}"
    except RuntimeError as e:  # From ensure_login_session
        return f"Runtime Error during login check: {e}"
    except Exception as e:  # Catch any other unexpected errors
        log.exception("Unexpected error during login status check.")
        return f"An unexpected error occurred during login check: {str(e)}"



@mcp.tool()
async def get_nodes(ctx: Context) -> list[str] | str:
    """
    Get ONLY the list of node IDs (names) without detailed information.

    Use this tool only when:
    - User specifically asks for "node IDs", "device names", or "list of devices"
    - You need just the names/IDs for reference

    For comprehensive device information, use get_node_details instead.
    """
    log.info("Fetching node list.")
    try:
        s = await ensure_login_session()
        nodes_dict = await asyncio.to_thread(s.get_nodes)
        node_ids = list(nodes_dict.keys())
        log.info(f"Found {len(node_ids)} nodes.")
        if not node_ids:
            return "No nodes found for this user."
        return node_ids
    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting nodes: {e}")
        return f"Error getting nodes: API error - {e}"
    # Network/SSL errors should be caught by ensure_login_session primarily
    except Exception as e:
        log.exception("Unexpected error getting nodes.")
        return f"Error getting nodes: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def get_node_status(ctx: Context, node_id: str) -> dict | str:
    """
    Get ONLY the online/offline status for a specific node.

    Use this tool only when:
    - User specifically asks about "status", "online", "offline" of a particular device
    - You already have other info and need just the status

    For comprehensive device information, use get_node_details instead.
    """
    log.info(f"Fetching status for node: {node_id}")
    try:
        s = await ensure_login_session()
        n = await asyncio.to_thread(rainmaker_node.Node, node_id, s)
        status_data = await asyncio.to_thread(n.get_node_status)
        log.info(f"Successfully fetched status for node: {node_id}")
        return status_data
    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting status for node {node_id}: {e}")
        return f"Error getting status for node {node_id}: API error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error getting status for node {node_id}.")
        return f"Error getting status for node {node_id}: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def get_params(ctx: Context, node_id: str) -> dict | str:
    """
    Get ONLY the current parameters (state) for a specific node.

    Use this tool only when:
    - User specifically asks for "parameters", "state", or "current values" of a particular device
    - You already have other info and need just the current state

    For comprehensive device information, use get_node_details instead.
    """
    log.info(f"Fetching parameters for node: {node_id}")
    try:
        s = await ensure_login_session()
        n = await asyncio.to_thread(rainmaker_node.Node, node_id, s)
        params_data = await asyncio.to_thread(n.get_node_params)
        if params_data is None:
            log.warning(f"get_node_params returned None for node {node_id}")
            return f"Error: Failed to retrieve parameters for node {node_id}. Node might be offline or an API error occurred."
        log.info(f"Successfully fetched parameters for node: {node_id}")
        return params_data
    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting params for node {node_id}: {e}")
        return f"Error getting parameters for node {node_id}: API error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error getting params for node {node_id}.")
        return f"Error getting parameters for node {node_id}: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def set_params(ctx: Context, node_id: str, params_dict: dict) -> str:
    """
    Set parameters for one or more nodes using a JSON object (dictionary).

    Parameters:
    - node_id: Single node ID or comma-separated list of node IDs (e.g., "node1" or "node1,node2,node3")
    - params_dict: Dictionary containing the parameters to set

    Example params_dict value:
    {'Thermostat': {'Power': False}}

    When multiple node IDs are provided, the same parameters will be applied to all specified nodes.
    This is useful for bulk operations like turning off multiple devices or setting common configurations.
    """
    node_ids = [nid.strip() for nid in node_id.split(',')]
    if len(node_ids) == 1:
        log.info(f"Attempting to set parameters for node: {node_ids[0]}")
    else:
        log.info(f"Attempting to set parameters for {len(node_ids)} nodes: {', '.join(node_ids)}")
    log.debug(f"Received params dictionary: {params_dict}")

    if not isinstance(params_dict, dict) or not params_dict:
        log.warning(f"Invalid or empty params_dict provided: {params_dict}")
        return "Error: Parameter data must be a non-empty JSON object (dictionary)."

    try:
        s = await ensure_login_session()
        n = await asyncio.to_thread(rainmaker_node.Node, node_id, s)  # Pass original comma-separated string
        success = await asyncio.to_thread(n.set_node_params, params_dict)

        if success:
            if len(node_ids) == 1:
                log.info(f"Successfully set parameters for node: {node_ids[0]}")
                return f"Parameters successfully updated for node {node_ids[0]}."
            else:
                log.info(f"Successfully set parameters for {len(node_ids)} nodes: {', '.join(node_ids)}")
                return f"Parameters successfully updated for {len(node_ids)} nodes: {', '.join(node_ids)}."
        else:
            log.warning(f"set_node_params returned False for node(s) {node_id}")
            if len(node_ids) == 1:
                return f"Error: Failed to set parameters for node {node_ids[0]}. The RainMaker API call did not succeed (check node status and parameters)."
            else:
                return f"Error: Failed to set parameters for nodes {', '.join(node_ids)}. The RainMaker API call did not succeed (check node status and parameters)."

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error setting params for node(s) {node_id}: {e}")
        return f"Error setting parameters for node(s) {node_id}: API error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error setting params for node(s) {node_id}.")
        return f"Error setting parameters for node(s) {node_id}: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def get_node_details(
    ctx: Context,
    node_id: str | None = None,
    fields: str | None = None,
    name: str | None = None,
    type_: str | None = None
) -> dict | list | str:
    """
    **PREFERRED TOOL** for getting comprehensive node information efficiently.
    Gets config, status, and params in a single API call instead of multiple separate calls.

    USAGE:
    - To get all nodes: set `node_id=None` (default).
    - To get a single node: set `node_id` to a single node ID string.
      - Only a single node ID is supported. Do NOT use a comma-separated list or array.
      - If the node is not found or not accessible, the result will be an empty dict or contain empty/unknown fields.

    FILTERING & FIELD SELECTION:
    - `fields`: comma-separated list of fields to include in the output (e.g. "node_id,name,type,config,params,status.connectivity,fw_version,mapping_timestamp").
    - `name`: substring match (matches user-visible name, extracted from params.{DeviceType}.Name).
    - `type_`: substring match (matches device type, from config.devices[].type).
    - `node_id`: single node ID string (for a single node), or None (for all nodes).

    MULTIPLE NODE FILTERING:
    - To filter for multiple node IDs, set `node_id=None` and use filtering (e.g. by name or type) in post-processing.
    - Passing a comma-separated list of node IDs is NOT supported and will result in an error.

    RETURN VALUE:
    - If a single node is requested, returns a dict (or empty dict if not found).
    - If all nodes are requested, returns a list of dicts (one per node).

    EXAMPLES:
    - Get all nodes, only node_id and name:
        get_node_details(ctx, fields="node_id,name")
    - Get a single node by ID:
        get_node_details(ctx, node_id="30EDA0E0AF48", fields="node_id,name,config")
    - Get all nodes of type 'lightbulb':
        get_node_details(ctx, type_="lightbulb", fields="node_id,name,type")
    """
    import copy
    log.info(f"Fetching detailed information for node: {node_id}")
    try:
        s = await ensure_login_session()

        # Fetch node(s) - always extract node_details array
        if node_id:
            if isinstance(node_id, (list, tuple, set)) or (isinstance(node_id, str) and ',' in node_id):
                return {"error": "Only a single node_id is allowed. For multiple nodes, use node_id=None and filter in post-processing."}
            details_data = await asyncio.to_thread(s.get_node_details_by_id, node_id)
        else:
            details_data = await asyncio.to_thread(s.get_node_details)

        if isinstance(details_data, dict) and 'node_details' in details_data:
            nodes = details_data['node_details']
        else:
            nodes = details_data if isinstance(details_data, list) else []

        # Parse fields
        if fields:
            field_list = [f.strip() for f in fields.split(',') if f.strip()]
        else:
            field_list = None  # None means return all fields

        # Helper: extract display name and type (from get_group_details)
        def get_device_info(node: dict) -> tuple[str, str]:
            try:
                devices = node.get("config", {}).get("devices", [])
                params = node.get("params", {})
                if devices and isinstance(devices, list):
                    device = devices[0]
                    device_name = device.get("name", "")  # e.g., "Light"
                    device_type = device.get("type", "Unknown")
                    user_visible_name = None
                    if device_name and device_name in params:
                        user_visible_name = params[device_name].get("Name")
                    if not user_visible_name:
                        user_visible_name = device_name or "Unnamed Device"
                    return user_visible_name, device_type
            except Exception as e:
                log.warning(f"Error extracting device info: {e}")
            return "Unknown Device", "Unknown"

        # Filtering logic
        filtered_nodes = []
        for node in nodes:
            # Filter by node_id (if node_id is a list, support that)
            if node_id and isinstance(node_id, (list, tuple, set)):
                if node.get("node_id") not in node_id:
                    continue
            # Filter by name (substring, from params)
            if name:
                display_name, _ = get_device_info(node)
                if name.lower() not in display_name.lower():
                    continue
            # Filter by type (substring, from device type)
            if type_:
                _, device_type = get_device_info(node)
                if type_.lower() not in device_type.lower():
                    continue
            # If fields specified, select only those fields
            if field_list:
                filtered = {}
                for field in field_list:
                    if field == "node_id":
                        filtered["node_id"] = node.get("node_id", "")
                    elif field == "name":
                        filtered["name"] = get_device_info(node)[0]
                    elif field == "type":
                        filtered["type"] = get_device_info(node)[1]
                    elif field == "config":
                        filtered["config"] = node.get("config", {})
                    elif field == "params":
                        filtered["params"] = node.get("params", {})
                    elif field == "status":
                        filtered["status"] = node.get("status", {})
                    elif field == "status.connectivity":
                        filtered.setdefault("status", {})["connectivity"] = node.get("status", {}).get("connectivity", {})
                    elif field == "config.info":
                        value = node.get("config", {}).get("info")
                        filtered[field] = value if value is not None else None
                    elif field.startswith("config.info."):
                        # e.g. config.info.name
                        parts = field.split('.')
                        value = node.get("config", {}).get("info", {})
                        for p in parts[2:]:
                            value = value.get(p, {}) if isinstance(value, dict) else {}
                        filtered[field] = value
                    elif field.startswith("params."):
                        # e.g. params.Light.Name
                        parts = field.split('.')
                        value = node.get("params", {})
                        for p in parts[1:]:
                            value = value.get(p, {}) if isinstance(value, dict) else {}
                        filtered[field] = value
                    else:
                        # fallback: top-level
                        filtered[field] = node.get(field, None)
                filtered_nodes.append(filtered)
            else:
                # No field filtering, return full node
                filtered_nodes.append(copy.deepcopy(node))

        # Return single node as dict, all as list
        if node_id and not isinstance(node_id, (list, tuple, set)):
            return filtered_nodes[0] if filtered_nodes else {}
        return filtered_nodes

    except (ValueError, ConnectionError, RuntimeError) as e:
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting node details: {e}")
        return f"Error getting node details: API error - {e}"
    except Exception as e:
        log.exception("Unexpected error getting node details.")
        return f"Error getting node details: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def get_schedules(ctx: Context, node_id: str) -> dict | str:
    """
    Get schedule information for a specific node.
    Returns the schedules configured for the node if any exist, along with support status.

    Response includes:
    - schedules_supported: Whether the node supports scheduling
    - schedules: Array of schedule objects with trigger and action details
    - schedule_count: Number of configured schedules

    Each schedule object contains:
    - id: Unique schedule identifier
    - name: Human-readable schedule name
    - enabled: Whether the schedule is active
    - triggers: Array of trigger conditions (format explained below)
    - action: What the schedule will do when triggered

    TRIGGER FORMAT GUIDE (for understanding schedule responses):
    - "m": Minutes since midnight (0-1439). Example: 480 = 8:00 AM, 1110 = 6:30 PM
    - "d": Day bitmap for which days to trigger:
      * 31 = Weekdays (Mon-Fri)
      * 96 = Weekends (Sat-Sun)
      * 127 = Every day
      * 0 = One-time only
      * Individual days: 1=Mon, 2=Tue, 4=Wed, 8=Thu, 16=Fri, 32=Sat, 64=Sun
    - "dd": Day of month (1-31)
    - "mm": Month bitmap (4095 = all months)
    - "rsec": Relative seconds from creation time
    - "ts": Exact Unix timestamp when schedule was created or will trigger

    Example: {"m": 1110, "d": 31} means "6:30 PM on weekdays"

    NOTE: Schedule actions use device type names (like "Light") not display names.
    See get_node_details for the mapping between device types and their display names.
    """
    log.info(f"Fetching schedules for node: {node_id}")

    try:
        s = await ensure_login_session()

        # Get node details for the specific node
        node_details = await asyncio.to_thread(s.get_node_details_by_id, node_id)

        # Use the shared utility function to extract schedule information
        schedule_info = await asyncio.to_thread(extract_schedules_from_node_details, node_details, node_id)

        log.info(f"Successfully fetched {schedule_info.get('schedule_count', 0)} schedules for node: {node_id}")
        return schedule_info

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting schedules for node {node_id}: {e}")
        return f"Error getting schedules for node {node_id}: API error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error getting schedules for node {node_id}.")
        return f"Error getting schedules for node {node_id}: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def set_schedule(ctx: Context, node_id: str, operation: str, schedule_id: str | None = None,
                      name: str | None = None, trigger: dict | None = None, action: dict | None = None,
                      info: str | None = None, flags: str | None = None) -> str:
    """
    Manage schedules for one or more nodes.

    Parameters:
    - node_id: Single node ID or comma-separated list of node IDs (e.g., "node1" or "node1,node2,node3")
    - operation: Operation to perform (add, edit, remove, enable, disable)
    - schedule_id: Schedule ID (required for edit, remove, enable, disable operations)
    - name: Schedule name (required for add operation, optional for edit)
    - trigger: Dictionary defining when to trigger (required for add, optional for edit)
    - action: Dictionary defining what to do (required for add, optional for edit)
    - info: Additional information for the schedule (optional)
    - flags: General purpose flags for the schedule (optional)

    When multiple node IDs are provided:
    - For 'add' operations: Creates the same schedule on all specified nodes with a common schedule ID
    - For 'edit/remove/enable/disable' operations: Applies the operation to the specified schedule on all nodes
    - This is useful for bulk schedule management across multiple devices

    TRIGGER FORMAT GUIDE:
    Time-based triggers use these fields:
    - "m": Minutes since midnight (0-1439). Example: 480 = 8:00 AM, 1110 = 6:30 PM
    - "d": Day bitmap for which days to trigger:
      * 31 = Weekdays (Mon-Fri)
      * 96 = Weekends (Sat-Sun)
      * 127 = Every day
      * 0 = One-time only
      * Individual days: 1=Mon, 2=Tue, 4=Wed, 8=Thu, 16=Fri, 32=Sat, 64=Sun
    - "dd": Day of month (1-31)
    - "mm": Month bitmap (4095 = all months)
    - "rsec": Relative seconds from now
    - "ts": Exact Unix timestamp

    COMMON TRIGGER EXAMPLES:
    - Daily 8:00 AM: {"m": 480, "d": 127}
    - Weekdays 6:30 PM: {"m": 1110, "d": 31}
    - Weekends 10:00 AM: {"m": 600, "d": 96}
    - One-time 7:00 PM: {"m": 1140, "d": 0}
    - 15th of every month at noon: {"m": 720, "dd": 15, "mm": 4095}
    - In 1 hour: {"rsec": 3600}

    ACTION EXAMPLES:
    - Turn on light: {"Light": {"Power": true}}
    - Set brightness: {"Light": {"Power": true, "Brightness": 80}}
    - Control thermostat: {"Thermostat": {"Power": true, "Temperature": 22}}

    NOTE: Action keys use device type names (like "Light") not display names.
    Use get_node_details to see device types in config.devices[].name.
    """
    node_ids = [nid.strip() for nid in node_id.split(',')]
    if len(node_ids) == 1:
        log.info(f"Setting schedule for node: {node_ids[0]}, operation: {operation}")
    else:
        log.info(f"Setting schedule for {len(node_ids)} nodes: {', '.join(node_ids)}, operation: {operation}")

    try:
        # Use the shared utility function to format schedule parameters
        params = await asyncio.to_thread(format_schedule_params,
            operation=operation,
            schedule_id=schedule_id,
            name=name,
            trigger=trigger,  # MCP provides dict directly, not JSON string
            action=action,    # MCP provides dict directly, not JSON string
            info=info,
            flags=flags,
            auto_generate_id=True
        )

        # Extract generated ID for 'add' operations
        generated_id = None
        if operation == 'add' and 'Schedule' in params and 'Schedules' in params['Schedule']:
            generated_id = params['Schedule']['Schedules'][0].get('id')

    except ValueError as e:
        error_msg = f"Error: {str(e)}"
        log.warning(error_msg)
        return error_msg

    try:
        s = await ensure_login_session()
        n = await asyncio.to_thread(rainmaker_node.Node, node_id, s)  # Pass original comma-separated string

        # Set the parameters on the node
        response = await asyncio.to_thread(n.set_node_params, params)

        # Determine if the operation was successful
        success = False
        if isinstance(response, dict) and response.get('status', '').lower() == 'success':
            success = True
        elif isinstance(response, bool) and response:
            success = True

        if success:
            op_str = {
                'add': 'added',
                'edit': 'updated',
                'remove': 'removed',
                'enable': 'enabled',
                'disable': 'disabled'
            }.get(operation, operation)

            if len(node_ids) == 1:
                result_msg = f"Schedule successfully {op_str} for node {node_ids[0]}."
                log.info(f"Successfully {op_str} schedule for node: {node_ids[0]}")
            else:
                result_msg = f"Schedule successfully {op_str} for {len(node_ids)} nodes: {', '.join(node_ids)}."
                log.info(f"Successfully {op_str} schedule for {len(node_ids)} nodes: {', '.join(node_ids)}")

            if operation == 'add' and generated_id:
                result_msg += f" Schedule ID: {generated_id}"

            return result_msg
        else:
            if isinstance(response, dict):
                error_msg = f"Error setting schedule: {response.get('description', 'Unknown error')}"
            else:
                error_msg = "Error setting schedule: Unexpected response format"
            log.warning(error_msg)
            return error_msg

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error setting schedule for node(s) {node_id}: {e}")
        return f"Error setting schedule for node(s) {node_id}: API error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error setting schedule for node(s) {node_id}.")
        return f"Error setting schedule for node(s) {node_id}: An unexpected error occurred - {str(e)}"


# --- Group Management Tools ---

@mcp.tool()
async def create_group(ctx: Context, name: str, group_type: str | None = None, description: str | None = None,
                      mutually_exclusive: bool = False, parent_group_id: str | None = None,
                      nodes: str | None = None, custom_data: str | None = None) -> str:
    """
    Create a new group (home, room, or custom group) using Python library API.

    Parameters:
    - name: Name of the group (required)
    - group_type: Type of group ('home', 'room', or custom type)
    - description: Description of the group (optional)
    - mutually_exclusive: Set mutually exclusive flag (recommended for homes and rooms)
    - parent_group_id: Parent group ID (required for rooms under a home)
    - nodes: Comma-separated list of node IDs to add to the group (optional)
    - custom_data: Custom data as JSON string (optional)

    Examples:
    - Create home: create_group("My Home", "home", mutually_exclusive=True)
    - Create room: create_group("Living Room", "room", mutually_exclusive=True, parent_group_id="home_id")
    """
    log.info(f"Creating group: {name} (type: {group_type})")

    try:
        s = await ensure_login_session()

        # Convert comma-separated nodes to list if provided
        node_list = None
        if nodes:
            node_list = [n.strip() for n in nodes.split(',') if n.strip()]

        # Parse custom_data if provided
        custom_data_dict = None
        if custom_data:
            try:
                custom_data_dict = json.loads(custom_data)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in custom_data: {e}"

        # Call Python library API directly
        result = await asyncio.to_thread(
            s.create_group,
            group_name=name,
            type_=group_type,
            description=description,
            mutually_exclusive=mutually_exclusive,
            parent_group_id=parent_group_id,
            nodes=node_list,
            custom_data=custom_data_dict
        )

        # Parse response and extract group information
        if isinstance(result, dict):
            group_id = result.get('group_id', 'unknown')
            status = result.get('status', 'unknown')

            if status == 'success' or group_id != 'unknown':
                log.info(f"Successfully created group: {name} with ID: {group_id}")
                success_msg = f"Group '{name}' created successfully with ID: {group_id}"

                # If nodes were specified, mention they were added
                if node_list:
                    success_msg += f" and {len(node_list)} nodes added"

                return success_msg
            else:
                error_msg = result.get('description', 'Unknown error occurred')
                log.error(f"Failed to create group {name}: {error_msg}")
                return f"Error creating group '{name}': {error_msg}"
        else:
            log.warning(f"Unexpected response format for group creation: {result}")
            return f"Group '{name}' created (unexpected response format)"

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error creating group {name}: {e}")
        return f"Error creating group '{name}': API error - {e}"
    except (NetworkError, SSLError, RequestTimeoutError) as e:
        log.error(f"Network/SSL error creating group {name}: {e}")
        return f"Error creating group '{name}': Connection error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error creating group {name}.")
        return f"Error creating group '{name}': An unexpected error occurred - {str(e)}"


async def add_nodes_to_group_hierarchically(group_id: str, node_ids: str) -> list[str]:
    """
    Helper function to add nodes to a group, handling parent-child hierarchy.
    If the target group has a parent, nodes are first added to the parent, then to the target group.
    Uses Python library API with standardized error handling.

    Returns a list of result messages.
    """
    results = []

    try:
        s = await ensure_login_session()

        # Convert node_ids string to list
        node_list = [n.strip() for n in node_ids.split(',') if n.strip()]
        log.info(f"Adding nodes {node_list} to group {group_id} with hierarchical support")

        # First, get the target group details to check if it has a parent
        log.info(f"Getting group details for {group_id}")
        try:
            group_data = await asyncio.to_thread(s.show_group, group_id, sub_groups=True)
            log.info(f"Group data retrieved for {group_id}")

            # Check if this group has a parent
            parent_group_id = None
            if isinstance(group_data, dict) and "groups" in group_data and len(group_data["groups"]) > 0:
                group_info = group_data["groups"][0]
                parent_group_id = group_info.get("parent_group_id")
                log.info(f"Group {group_id} has parent: {parent_group_id}")

            # If there's a parent, add nodes to parent first
            if parent_group_id:
                log.info(f"Adding nodes to parent group {parent_group_id} first")
                try:
                    parent_resp = await asyncio.to_thread(s.add_nodes_to_group, parent_group_id, node_list)

                    # Parse parent response
                    if isinstance(parent_resp, dict):
                        status = parent_resp.get('status', 'unknown')
                        if status == 'success':
                            results.append(f"Added nodes to parent group {parent_group_id}")
                            log.info(f"Successfully added nodes to parent group {parent_group_id}")
                        else:
                            error_msg = parent_resp.get('description', 'Unknown error')
                            log.warning(f"Failed to add nodes to parent group {parent_group_id}: {error_msg}")
                            results.append(f"Warning: Could not add to parent group {parent_group_id}: {error_msg}")
                    else:
                        results.append(f"Added nodes to parent group {parent_group_id} (unexpected response format)")

                except HttpErrorResponse as e:
                    log.warning(f"HTTP error adding nodes to parent group {parent_group_id}: {e}")
                    results.append(f"Warning: Could not add to parent group {parent_group_id}: API error - {e}")
                except Exception as parent_error:
                    log.warning(f"Error adding nodes to parent group {parent_group_id}: {parent_error}")
                    # Continue anyway, maybe the nodes are already in the parent
                    results.append(f"Warning: Could not add to parent group {parent_group_id}: {parent_error}")

        except HttpErrorResponse as e:
            log.warning(f"HTTP error getting group details for {group_id}: {e}, proceeding without parent check")
            results.append(f"Warning: Could not check parent group: API error - {e}")
        except Exception as e:
            log.warning(f"Could not get group details for {group_id}: {e}, proceeding without parent check")
            results.append(f"Warning: Could not check parent group: {e}")

        # Now add nodes to the target group
        log.info(f"Adding nodes to target group {group_id}")
        try:
            target_resp = await asyncio.to_thread(s.add_nodes_to_group, group_id, node_list)

            # Parse target response
            if isinstance(target_resp, dict):
                status = target_resp.get('status', 'unknown')
                if status == 'success':
                    results.append(f"Added {len(node_list)} nodes to target group {group_id}: {', '.join(node_list)}")
                    log.info(f"Successfully added nodes to target group {group_id}")
                else:
                    error_msg = target_resp.get('description', 'Unknown error')
                    log.error(f"Failed to add nodes to target group {group_id}: {error_msg}")
                    results.append(f"Error adding nodes to target group {group_id}: {error_msg}")
            else:
                results.append(f"Added {len(node_list)} nodes to target group {group_id} (unexpected response format)")
                log.warning(f"Unexpected response format for target group addition: {target_resp}")

        except HttpErrorResponse as e:
            log.error(f"HTTP error adding nodes to target group {group_id}: {e}")
            results.append(f"Error adding nodes to target group {group_id}: API error - {e}")
        except Exception as target_error:
            log.error(f"Failed to add nodes to target group {group_id}: {target_error}")
            results.append(f"Error adding nodes to target group {group_id}: {target_error}")

        return results

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        log.error(f"Session error in hierarchical node addition for group {group_id}: {e}")
        return [f"Session error: {e}"]
    except (NetworkError, SSLError, RequestTimeoutError) as e:
        log.error(f"Network/SSL error in hierarchical node addition for group {group_id}: {e}")
        return [f"Connection error: {e}"]
    except Exception as e:
        log.exception(f"Unexpected error in hierarchical node addition for group {group_id}")
        return [f"Error in hierarchical node addition: {str(e)}"]


@mcp.tool()
async def add_device_to_room(ctx: Context, device_node_id: str, room_group_id: str) -> str:
    """
    Add a device to a room with automatic parent group handling.

    This function automatically handles the ESP RainMaker hierarchy requirement:
    1. First adds the device to the parent group (e.g., "My Home")
    2. Then adds the device to the target room group (e.g., "Kitchen")

    Parameters:
    - device_node_id: The node ID of the device to add
    - room_group_id: The group ID of the room to add the device to

    This is a convenience function that makes the hierarchical behavior explicit.
    """
    log.info(f"Adding device {device_node_id} to room {room_group_id} with hierarchical support")

    try:
        await ensure_login_session()

        # Use the hierarchical helper function
        hierarchical_results = await add_nodes_to_group_hierarchically(room_group_id, device_node_id)

        # Check if there were any errors
        error_results = [r for r in hierarchical_results if r.startswith("Error")]
        if error_results:
            return f"Error adding device to room: {'; '.join(error_results)}"

        # Return success message with details
        success_message = f"Successfully added device {device_node_id} to room {room_group_id}."
        if len(hierarchical_results) > 1:
            success_message += f" Details: {'; '.join(hierarchical_results)}"

        return success_message

    except (ValueError, ConnectionError, RuntimeError) as e:
        return str(e)
    except Exception as e:
        log.exception(f"Unexpected error adding device {device_node_id} to room {room_group_id}")
        return f"Error adding device to room: An unexpected error occurred - {str(e)}"


@mcp.tool()
async def update_group(ctx: Context, group_id: str, name: str | None = None, description: str | None = None,
                      custom_data: str | None = None, add_nodes: str | None = None, remove_nodes: str | None = None) -> str:
    """
    Edit an existing group's properties and manage nodes using Python library API.

    Parameters:
    - group_id: ID of the group to edit (required)
    - name: New name for the group (optional)
    - description: New description for the group (optional)
    - custom_data: New custom data as JSON string (optional)
    - add_nodes: Comma-separated list of node IDs to add to the group (optional)
    - remove_nodes: Comma-separated list of node IDs to remove from the group (optional)

    At least one parameter must be provided.
    """
    log.info(f"Updating group: {group_id}")

    if not any([name, description, custom_data, add_nodes, remove_nodes]):
        return "Error: At least one of name, description, custom_data, add_nodes, or remove_nodes must be provided."

    results = []

    try:
        s = await ensure_login_session()

        # Handle property updates (name, description, custom_data)
        if any([name, description, custom_data]):
            # Parse custom_data if provided
            custom_data_dict = None
            if custom_data:
                try:
                    custom_data_dict = json.loads(custom_data)
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON in custom_data: {e}"

            # Call Python library API for property updates
            try:
                result = await asyncio.to_thread(
                    s.edit_group,
                    group_id=group_id,
                    group_name=name,
                    description=description,
                    custom_data=custom_data_dict
                )

                # Parse response
                if isinstance(result, dict):
                    status = result.get('status', 'unknown')
                    if status == 'success':
                        results.append("Group properties updated successfully")
                        log.info(f"Successfully updated group properties: {group_id}")
                    else:
                        error_msg = result.get('description', 'Unknown error occurred')
                        log.error(f"Failed to update group properties {group_id}: {error_msg}")
                        return f"Error updating group properties for '{group_id}': {error_msg}"
                else:
                    results.append("Group properties updated (unexpected response format)")
                    log.warning(f"Unexpected response format for group property update: {result}")

            except HttpErrorResponse as e:
                log.error(f"HTTP error updating group properties {group_id}: {e}")
                return f"Error updating group properties for '{group_id}': API error - {e}"

        # Handle adding nodes (with hierarchical support)
        if add_nodes:
            hierarchical_results = await add_nodes_to_group_hierarchically(group_id, add_nodes)

            # Check if there were any errors in the hierarchical addition
            error_results = [r for r in hierarchical_results if r.startswith("Error")]
            if error_results:
                return f"Error adding nodes to group '{group_id}': {'; '.join(error_results)}"

            results.extend(hierarchical_results)

        # Handle removing nodes using Python library API
        if remove_nodes:
            node_list = [n.strip() for n in remove_nodes.split(',') if n.strip()]

            try:
                result = await asyncio.to_thread(s.remove_nodes_from_group, group_id, node_list)

                # Parse response
                if isinstance(result, dict):
                    status = result.get('status', 'unknown')
                    if status == 'success':
                        results.append(f"Removed {len(node_list)} nodes: {', '.join(node_list)}")
                        log.info(f"Successfully removed nodes from group {group_id}: {remove_nodes}")
                    else:
                        error_msg = result.get('description', 'Unknown error occurred')
                        log.error(f"Failed to remove nodes from group {group_id}: {error_msg}")
                        return f"Error removing nodes from group '{group_id}': {error_msg}"
                else:
                    results.append(f"Removed {len(node_list)} nodes (unexpected response format)")
                    log.warning(f"Unexpected response format for node removal: {result}")

            except HttpErrorResponse as e:
                log.error(f"HTTP error removing nodes from group {group_id}: {e}")
                return f"Error removing nodes from group '{group_id}': API error - {e}"

        return f"Group '{group_id}' updated successfully. " + "; ".join(results)

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except (NetworkError, SSLError, RequestTimeoutError) as e:
        log.error(f"Network/SSL error updating group {group_id}: {e}")
        return f"Error updating group '{group_id}': Connection error - {e}"
    except Exception as e:
        log.exception(f"Unexpected error updating group {group_id}.")
        return f"Error updating group '{group_id}': An unexpected error occurred - {str(e)}"


@mcp.tool()
async def get_group_details(
    ctx: Context,
    group_id: str | None = None,
    include_nodes: bool = False,
    fields: list[str] | None = None,
    node_fields: list[str] | None = None
) -> dict | str:
    """
    Get comprehensive group information using Python library API.

    Parameters:
    - group_id: ID of specific group to show (optional - if None, lists all groups)
    - include_nodes: Include detailed node information for groups
    - fields: List of group/sub-group keys to include (if None, includes all fields)
    - node_fields: List of node keys to include (if None, includes all node fields)

    When group_id is None: Lists all groups with hierarchy
    When group_id is provided: Shows detailed information for that specific group
    When include_nodes is True: Includes comprehensive node details within groups

    ---
    **IMPORTANT USAGE GUIDELINES:**

    1. For home/room structure overview (recommended for most queries):
       ```python
       {
           "include_nodes": true,
           "fields": ["group_id", "group_name", "type", "total", "sub_groups", "node_details"],
           "node_fields": ["node_id", "name", "type"]
       }
       ```

    2. For home/room structure with basic device info:
       ```python
       {
           "include_nodes": true,
           "fields": ["group_id", "group_name", "type", "total", "sub_groups", "node_details"],
           "node_fields": ["node_id", "name", "type", "model", "fw_version"]
       }
       ```

    3. For detailed technical information:
       ```python
       {
           "include_nodes": true,
           "fields": ["group_id", "group_name", "type", "total", "sub_groups", "node_details",
                     "is_matter", "fabric_id", "primary", "mutually_exclusive"],
           "node_fields": ["node_id", "name", "type", "model", "fw_version", "status", "params"]
       }
       ```

    **Common Use Cases:**
    | Query Type          | Recommended Fields                                  |
    |--------------------|---------------------------------------------------|
    | "Show my home"     | Basic fields (option 1) to avoid large responses  |
    | "List my devices"  | Basic fields (option 1) for clear device listing  |
    | "Check my rooms"   | Basic fields (option 1) for room structure        |
    | "Device details"   | Detailed fields (option 3) for full information   |

    Note: When fields/node_fields are not provided, defaults to summary mode (basic fields)
    to avoid overwhelming responses.
    """
    log.info(f"Fetching group details. group_id={group_id}, include_nodes={include_nodes}")

    try:
        s = await ensure_login_session()

        # Default essential fields if none specified
        if fields is None:
            fields = [
                "group_id", "group_name", "type", "total", "sub_groups",
                "is_matter", "fabric_id", "primary", "mutually_exclusive",
                "parent_group_id", "description"
            ]
        # Always ensure these fields are included for proper structure
        if "sub_groups" not in fields:
            fields.append("sub_groups")
        if include_nodes and "node_details" not in fields:
            fields.append("node_details")

        # Default node fields if none specified
        if node_fields is None:
            node_fields = ["node_id", "name", "type"]

        # Helper function to get device name and type from node
        def get_device_info(node: dict) -> tuple[str, str]:
            try:
                devices = node.get("config", {}).get("devices", [])
                params = node.get("params", {})
                if devices and isinstance(devices, list):
                    device = devices[0]
                    device_name = device.get("name", "")  # e.g., "Light"
                    device_type = device.get("type", "Unknown")  # Use device type as requested

                    # Get the user-given name from params
                    user_visible_name = None
                    if device_name and device_name in params:
                        user_visible_name = params[device_name].get("Name")
                    if not user_visible_name:
                        user_visible_name = device_name or "Unnamed Device"

                    return user_visible_name, device_type
            except Exception as e:
                log.warning(f"Error extracting device info: {e}")
            return "Unknown Device", "Unknown"

        # Helper function to filter node details
        def filter_node(node: dict) -> dict:
            if not node_fields:
                return node

            # Get proper device name and type first
            display_name, device_type = get_device_info(node)

            # Create filtered dict with only requested fields
            filtered = {}

            # Add standard fields if requested
            if "node_id" in node_fields:
                filtered["node_id"] = node.get("node_id", "")
            if "name" in node_fields:
                filtered["name"] = display_name  # Use extracted name
            if "type" in node_fields:
                filtered["type"] = device_type   # Use extracted type
            if "model" in node_fields:
                filtered["model"] = node.get("model", "")
            if "fw_version" in node_fields:
                filtered["fw_version"] = node.get("fw_version", "")
            if "status" in node_fields:
                filtered["status"] = node.get("status", {})
            if "params" in node_fields:
                filtered["params"] = node.get("params", {})

            return filtered

        # Helper function to recursively filter groups
        def filter_group_recursive(group: dict) -> dict:
            if not group:
                return group

            # Filter top-level fields
            filtered = {k: v for k, v in group.items() if k in fields}

            # Handle node_details if present
            if include_nodes and "node_details" in group:
                if isinstance(group["node_details"], list):
                    filtered["node_details"] = [
                        filter_node(node) for node in group["node_details"]
                    ]
                elif isinstance(group["node_details"], dict):
                    filtered["node_details"] = {
                        k: filter_node(v) for k, v in group["node_details"].items()
                    }
                else:
                    filtered["node_details"] = group["node_details"]

            # Handle sub_groups recursively
            if "sub_groups" in group and group["sub_groups"]:
                filtered["sub_groups"] = [
                    filter_group_recursive(sub_group)
                    for sub_group in group["sub_groups"]
                ]

            return filtered

        # Fetch the initial group data
        if group_id:
            groups = await asyncio.to_thread(s.list_groups, sub_groups=True)
            # Find the specific group
            target_group = None
            for group in groups:
                if group.get("group_id") == group_id:
                    target_group = group
                    break
            if not target_group:
                return f"Group not found with ID: {group_id}"
            groups = [target_group]
        else:
            groups = await asyncio.to_thread(s.list_groups, sub_groups=True)

        # If nodes are requested, fetch them for each group and sub-group
        if include_nodes:
            for group in groups:
                # Fetch nodes for main group
                group_id = group.get("group_id")
                if group_id:
                    try:
                        nodes = await asyncio.to_thread(
                            s.list_nodes_in_group,
                            group_id,
                            node_details=True,
                            sub_groups=True
                        )
                        # Add nodes to the group
                        if isinstance(nodes, dict) and "groups" in nodes:
                            for g in nodes["groups"]:
                                if g["group_id"] == group_id and "node_details" in g:
                                    group["node_details"] = g["node_details"]
                                    break
                    except Exception as e:
                        log.warning(f"Error fetching nodes for group {group_id}: {e}")
                        group["node_details"] = []

                # Fetch nodes for sub-groups
                if "sub_groups" in group:
                    for sub_group in group["sub_groups"]:
                        sub_group_id = sub_group.get("group_id")
                        if sub_group_id:
                            try:
                                sub_nodes = await asyncio.to_thread(
                                    s.list_nodes_in_group,
                                    sub_group_id,
                                    node_details=True,
                                    sub_groups=True
                                )
                                # Add nodes to the sub-group
                                if isinstance(sub_nodes, dict) and "groups" in sub_nodes:
                                    for g in sub_nodes["groups"]:
                                        if g["group_id"] == sub_group_id and "node_details" in g:
                                            sub_group["node_details"] = g["node_details"]
                                            break
                            except Exception as e:
                                log.warning(f"Error fetching nodes for sub-group {sub_group_id}: {e}")
                                sub_group["node_details"] = []

        # Apply filtering
        if isinstance(groups, list):
            filtered_groups = [filter_group_recursive(group) for group in groups]
        else:
            filtered_groups = filter_group_recursive(groups)

        log.info("Successfully fetched and filtered group details")
        return filtered_groups[0] if group_id and filtered_groups else filtered_groups

    except (ValueError, ConnectionError, RuntimeError) as e:  # From ensure_login_session
        return str(e)
    except HttpErrorResponse as e:
        log.error(f"HTTP error getting group details: {e}")
        return f"Error getting group details: API error - {e}"
    except Exception as e:
        log.exception("Unexpected error getting group details")
        return f"Error getting group details: An unexpected error occurred - {str(e)}"

