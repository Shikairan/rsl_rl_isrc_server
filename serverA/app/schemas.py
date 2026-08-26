from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class GroupInfo(BaseModel):
    group_id: str
    nfs_host: str
    nfs_export_path: str
    local_mount_hint: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    nfs_host: str
    nfs_export_path: str
    groups: list[GroupInfo] = Field(default_factory=list)
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


class GroupMountInfo(BaseModel):
    group_id: str
    container_path: str


class ContainerResponse(BaseModel):
    server_b_endpoint: str
    obs_pub_endpoint: str | None = None
    tensorboard_endpoint: str | None = None
    container_status: str
    container_name: str
    nfs_mount_path: str = Field(default="/workspace")
    group_mounts: list[GroupMountInfo] = Field(default_factory=list)


class StopResponse(BaseModel):
    status: str
