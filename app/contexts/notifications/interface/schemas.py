"""Schémas HTTP du module Notifications."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.notifications.domain.aggregates import Device
from app.contexts.notifications.domain.enums import DevicePlatform


class RegisterDeviceBody(BaseModel):
    token: str = Field(examples=["fcm-registration-token…"])
    platform: DevicePlatform = Field(default=DevicePlatform.ANDROID)


class UnregisterDeviceBody(BaseModel):
    token: str


class DeviceView(BaseModel):
    id: UUID
    platform: str
    last_seen_at: datetime

    @classmethod
    def from_domain(cls, d: Device) -> DeviceView:
        return cls(id=d.id, platform=d.platform.value, last_seen_at=d.last_seen_at)


class DeviceListView(BaseModel):
    total: int
    devices: list[DeviceView]

    @classmethod
    def from_domain(cls, items: list[Device]) -> DeviceListView:
        return cls(total=len(items), devices=[DeviceView.from_domain(d) for d in items])
