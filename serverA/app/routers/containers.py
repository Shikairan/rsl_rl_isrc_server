from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import AuthError, parse_token
from app.container_service import ContainerNotFound, HealthCheckFailed
from app.docker_mgr import DockerError
from app.nfs import NfsError
from app.ports import PortPoolExhausted
from app.schemas import ContainerResponse, ContainerStartRequest, ErrorResponse, StopResponse

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": "missing token"})
    try:
        return parse_token(request.app.state.settings, creds.credentials)
    except AuthError:
        raise HTTPException(status_code=401, detail={"error": "invalid token"}) from None


def _require_docker(request: Request) -> None:
    if not request.app.state.settings.server.docker.enabled:
        raise HTTPException(
            status_code=503,
            detail={"error": "docker disabled; set server.docker.enabled=true"},
        )


def _svc(request: Request):
    _require_docker(request)
    return request.app.state.containers


@router.post(
    "/containers/start",
    response_model=ContainerResponse,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def start_container(
    body: ContainerStartRequest,
    request: Request,
    username: str = Depends(current_user),
) -> ContainerResponse:
    svc = _svc(request)
    try:
        return svc.start(username, body)
    except NfsError as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except PortPoolExhausted as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except HealthCheckFailed as exc:
        raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc
    except DockerError as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc


@router.get("/containers/current", response_model=ContainerResponse)
def current_container(request: Request, username: str = Depends(current_user)) -> ContainerResponse:
    try:
        return _svc(request).current(username)
    except ContainerNotFound:
        raise HTTPException(status_code=404, detail={"error": "no container"}) from None


@router.post("/containers/stop", response_model=StopResponse)
def stop_container(request: Request, username: str = Depends(current_user)) -> StopResponse:
    try:
        _svc(request).stop(username)
    except ContainerNotFound:
        raise HTTPException(status_code=404, detail={"error": "no container"}) from None
    except DockerError as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc
    return StopResponse(status="stopped")
