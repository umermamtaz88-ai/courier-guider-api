from enum import Enum


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL_WRITE = "external_write"


TOOL_REGISTRY: dict[str, Permission] = {
    "search_knowledge": Permission.READ,
    "search_web": Permission.READ,
    "get_policy": Permission.READ,
    "get_shipment": Permission.READ,
    "get_tracking": Permission.READ,
    "get_quote": Permission.READ,
    "get_provider": Permission.READ,
    "get_documents": Permission.READ,
    "compare_providers": Permission.READ,
    "create_task": Permission.WRITE,
    "update_task": Permission.WRITE,
    "record_event": Permission.WRITE,
    "send_email": Permission.EXTERNAL_WRITE,
    "create_booking": Permission.EXTERNAL_WRITE,
    "submit_external_request": Permission.EXTERNAL_WRITE,
}


def is_tool_allowed(tool_name: str, allowed: list[str]) -> bool:
    return tool_name in allowed and tool_name in TOOL_REGISTRY
