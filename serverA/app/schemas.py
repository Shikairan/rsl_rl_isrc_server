from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    nfs_host: str
    nfs_export_path: str
    server_b_endpoint: str | None = None
    obs_pub_endpoint: str | None = None
    tensorboard_endpoint: str | None = None


class ErrorResponse(BaseModel):
    error: str


class ContainerStartRequest(BaseModel):
    image: str
    gpu_count: int = 0
    cpu: str | None = None
    memory: str | None = None


class ContainerResponse(BaseModel):
    server_b_endpoint: str
    obs_pub_endpoint: str | None = None
    tensorboard_endpoint: str | None = None
    container_status: str
    container_name: str
    nfs_mount_path: str = Field(default="/workspace")


class StopResponse(BaseModel):
    status: str
