from typing import Any


def success_response(
    data: Any = None,
    *,
    message: str = "success",
) -> dict[str, Any]:
    return {
        "code": "SUCCESS",
        "message": message,
        "data": data,
    }

