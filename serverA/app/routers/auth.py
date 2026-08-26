from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.auth import AuthError, authenticate, issue_token
from app.schemas import ErrorResponse, GroupInfo, LoginRequest, LoginResponse

router = APIRouter()
logger = logging.getLogger(__name__)


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
        logger.warning("login failed username=%s", body.username)
        raise HTTPException(status_code=401, detail={"error": "invalid credentials"}) from None
    token, expires_at = issue_token(settings, body.username)
    endpoint = None
    obs_endpoint = None
    tb_endpoint = None
    svc = getattr(request.app.state, "containers", None)
    if svc is not None and settings.server.docker.enabled:
        endpoint, obs_endpoint, tb_endpoint = svc.running_endpoints(body.username)
    logger.info("login ok username=%s", body.username)
    groups = [
        GroupInfo(
            group_id=group_id,
            nfs_host=group.nfs_host,
            nfs_export_path=group.nfs_export_path,
            local_mount_hint=group.local_mount_path,
        )
        for group_id, group in settings.groups_for_user(body.username)
    ]
    return LoginResponse(
        token=token,
        expires_at=expires_at,
        nfs_host=user.nfs_host,
        nfs_export_path=user.nfs_export_path,
        groups=groups,
        server_b_endpoint=endpoint,
        obs_pub_endpoint=obs_endpoint,
        tensorboard_endpoint=tb_endpoint,
    )
