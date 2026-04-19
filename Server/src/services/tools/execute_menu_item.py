"""
Defines the execute_menu_item tool for executing and reading Unity Editor menu items.
"""
from typing import Annotated, Any

from fastmcp import Context
from mcp.types import ToolAnnotations

from models import MCPResponse
from services.registry import mcp_for_unity_tool
from services.tools import get_unity_instance_from_context
from transport.unity_transport import send_with_unity_instance
from transport.legacy.unity_connection import async_send_command_with_retry


@mcp_for_unity_tool(
    description=(
        "Execute a Unity menu item by path (e.g., 'File/Save Project', 'Tools/MyTool'). "
        "`menu_path` is required and must be a bare string — never null."
    ),
    annotations=ToolAnnotations(
        title="Execute Menu Item",
        destructiveHint=True,
    ),
)
async def execute_menu_item(
    ctx: Context,
    menu_path: Annotated[
        str,
        "Menu path to execute, e.g. 'File/Save Project' or 'Tools/MyTool'. Required."
    ] = "",
) -> MCPResponse | dict[str, Any]:
    # Fast-fail on empty menu_path to prevent null-loops: schemas that advertise
    # nullability encourage models to emit `null` and retry forever.
    if not menu_path or not menu_path.strip():
        return {
            "success": False,
            "message": (
                "execute_menu_item requires a non-empty `menu_path`. "
                "Do NOT pass null — pass a bare string like "
                "'Tools/Setup Prototype Scene' or 'File/Save Project'. "
                "If you don't know the path, run the menu command from the Unity "
                "Editor once and use that exact path."
            ),
        }

    unity_instance = await get_unity_instance_from_context(ctx)
    params_dict: dict[str, Any] = {"menuPath": menu_path.strip()}
    result = await send_with_unity_instance(
        async_send_command_with_retry, unity_instance, "execute_menu_item", params_dict
    )
    return MCPResponse(**result) if isinstance(result, dict) else result
