from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from footballpulse_api_gateway.auth import TokenService


class AuthServicePort(Protocol):
    tokens: TokenService

    def authenticate(self, username: str, password: str) -> str: ...


class TokenRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


def create_auth_app(service: AuthServicePort) -> FastAPI:
    app = FastAPI(title="FootballPulse Authentication API", version="0.1.0")

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_: Request, __: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_CREDENTIALS", "message": "invalid credentials"}},
        )

    @app.post("/auth/token", response_model=TokenResponse)
    async def issue_token(request: TokenRequest) -> TokenResponse:
        try:
            token = service.authenticate(request.username, request.password)
        except ValueError as error:
            raise PermissionError from error

        # AuthService exposes the token service so the response stays aligned
        # with the claims actually issued, instead of duplicating TTL config.
        claims = service.tokens.decode(token)
        expires_in = max(0, int((claims.expires_at - claims.issued_at).total_seconds()))
        role = claims.role.value
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            role=role,
        )

    return app
