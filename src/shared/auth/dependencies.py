"""Authentication dependencies.

In development (``AUTH_ENABLED=false``) a fixed stub user is returned so
routers work without a token.  Set ``AUTH_ENABLED=true`` and replace
``_get_real_user`` with your real JWT validation to enable auth — no router
changes required.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


class CurrentUser:
    """Lightweight representation of an authenticated caller."""

    def __init__(self, sub: str, roles: list[str]) -> None:
        self.sub = sub
        self.roles = roles

    def __repr__(self) -> str:
        return f"CurrentUser(sub={self.sub!r}, roles={self.roles!r})"


_STUB_USER = CurrentUser(sub="dev-stub@tmf.local", roles=["admin"])


async def _get_real_user(token: str) -> CurrentUser:  # pragma: no cover
    """Validate a JWT bearer token and return the caller.

    Replace the body of this function with real ``python-jose`` validation
    when ``AUTH_ENABLED`` is set to true.
    """
    from jose import JWTError, jwt  # noqa: PLC0415

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        sub: str = payload.get("sub")  # type: ignore[assignment]
        if sub is None:
            raise credentials_exception
        roles: list[str] = payload.get("roles", [])
        return CurrentUser(sub=sub, roles=roles)
    except JWTError as exc:
        raise credentials_exception from exc


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> CurrentUser:
    """FastAPI dependency — returns the current caller.

    - If ``AUTH_ENABLED=false`` (default in dev) → returns the stub user.
    - If ``AUTH_ENABLED=true`` → validates the bearer token.
    """
    if not settings.auth_enabled:
        return _STUB_USER

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await _get_real_user(token)
