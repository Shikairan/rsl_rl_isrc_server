from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.auth import AuthError, authenticate, issue_token
from app.schemas import ErrorResponse, LoginRequest, LoginResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}},
)
def login(body: LoginRequest, request: Request) -> LoginResponse:
    settings = request.app.state.settings
    try:
        user = authenticate(settings, body.username, body.password)
    except AuthError:
        raise HTTPException(status_code=401, detail={"error": "invalid credentials"}) from None
    token, expires_at = issue_token(settings, body.username)
    endpoint = None
    obs_endpoint = None
    svc = getattr(request.app.state, "containers", None)
    if svc is not None and settings.server.docker.enabled:
        endpoint, obs_endpoint = svc.running_endpoints(body.username)
    return LoginResponse(
        token=token,
        expires_at=expires_at,
        nfs_host=user.nfs_host,
        nfs_export_path=user.nfs_export_path,
        server_b_endpoint=endpoint,
        obs_pub_endpoint=obs_endpoint,
    )
