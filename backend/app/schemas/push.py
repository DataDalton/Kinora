"""Request and response bodies for the Web Push endpoints."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=1, max_length=255)
    auth: str = Field(..., min_length=1, max_length=255)


class PushSubscribeRequest(BaseModel):
    """The PushSubscription JSON from the browser, plus an optional device name."""

    endpoint: str = Field(..., min_length=1, max_length=2048)
    keys: PushSubscriptionKeys
    label: Optional[str] = Field(default=None, max_length=255)


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2048)


class PushDevice(BaseModel):
    id: int
    label: Optional[str] = None
    endpoint: str
    enabled: bool
    createdAt: datetime
    lastUsedAt: Optional[datetime] = None


class PushDeviceUpdate(BaseModel):
    """Partial device update. Only the fields sent are changed."""

    enabled: Optional[bool] = None
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)


class PushTestRequest(BaseModel):
    """Limit the test to one device. All of the user's enabled devices are used otherwise."""

    deviceId: Optional[int] = None


class PushTestResult(BaseModel):
    sent: int
    failed: int
    removed: int


class PushCategoryPreference(BaseModel):
    key: str
    label: str
    description: str
    enabled: bool


class PushPreferences(BaseModel):
    categories: List[PushCategoryPreference]


class PushPreferencesUpdate(BaseModel):
    """Category keys mapped to on or off. Keys not sent keep their current value."""

    types: Dict[str, bool]


class VapidPublicKey(BaseModel):
    publicKey: str
