from typing import Optional

from pydantic import Field

from ..base import FrigateBaseModel

__all__ = ["NotificationConfig"]


class NotificationConfig(FrigateBaseModel):
    enabled: bool = Field(
        default=False,
        title="Enable notifications",
        description="Enable or disable notifications for all cameras; can be overridden per-camera.",
    )
    email: Optional[str] = Field(
        default=None,
        title="Notification email",
        description="Email address used for push notifications or required by certain notification providers.",
    )
    cooldown: int = Field(
        default=0,
        ge=0,
        title="Cooldown period",
        description="Cooldown (seconds) between notifications to avoid spamming recipients.",
    )
    enabled_in_config: Optional[bool] = Field(
        default=None,
        title="Original notifications state",
        description="Indicates whether notifications were enabled in the original static configuration.",
    )
    # Weight-based cooldown configuration
    weight_decay_days: int = Field(
        default=3, ge=1, title="Days after which notification weights start to decay."
    )
    weight_factor: float = Field(
        default=0.2, ge=0.0, le=2.0, title="Cooldown increase factor per weight unit (0.2 = 20% increase)."
    )
    weight_max_factor: float = Field(
        default=3.0, ge=1.0, le=10.0, title="Maximum cooldown multiplier (3.0 = max 300% of base cooldown)."
    )
    weight_time_slots: int = Field(
        default=24, ge=1, le=24, title="Number of time slots per day for weight tracking (typically 24 for hourly)."
    )
