# app/core/decorators.py
"""
Fastango — Route Decorators
"""

from collections.abc import Callable
from functools import wraps

from app.core.constants import SUCCESS_MSG
from app.core.responses import success_response


def api_response() -> Callable:
    """Wrap a handler's return value in the standard response envelope.

    The handler returns `(data, message)` — or bare data when the generic
    message is fine — and this attaches {error, message, data}. A falsy message
    falls back to SUCCESS_MSG, so the wording always travels with whatever
    produced the result instead of being configured per route.

        @router.post("/login", response_model=APIResponse[TokenOutSchema])
        @api_response()
        async def login(request: Request, payload: LoginSchema):
            return await AuthService(payload).login()   # -> (tokens, "Login successful.")

    Errors are deliberately NOT caught here. A decorator only sees exceptions
    raised inside the handler body, so anything from a dependency, the auth
    middleware, or request validation would bypass it — those all go through the
    handlers in app/exceptions.py, which cover every path.

    Do not apply this to endpoints returning a Response subclass (FileResponse,
    StreamingResponse); their body is already final and must not be enveloped.
    """

    def decorator(func: Callable) -> Callable:
        # @wraps is load-bearing, not hygiene: FastAPI resolves the endpoint
        # signature via inspect.signature(), which follows __wrapped__. Without
        # it FastAPI sees (*args, **kwargs), binds nothing, and the request
        # body never reaches the handler.
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            data, message = result if isinstance(result, tuple) else (result, None)
            return success_response(data=data, message=message or SUCCESS_MSG)

        # FastAPI >=0.89 infers response_model from the return annotation, and
        # @wraps just copied the handler's -> tuple[dict, str] onto the wrapper.
        # Drop it so the explicit response_model= is the only source.
        wrapper.__annotations__ = {k: v for k, v in func.__annotations__.items() if k != "return"}
        return wrapper

    return decorator
