from typing import Optional

from pydantic import BaseModel, Field


class SendNotificationBody(BaseModel):
    title: str = Field(title="Notification title", max_length=200)
    message: str = Field(title="Notification message", max_length=500)
    direct_url: Optional[str] = Field(
        title="Direct URL to open when notification is clicked",
        default="",
        max_length=500
    )
    image: Optional[str] = Field(
        title="Image URL to display in notification",
        default="",
        max_length=500
    )
    ttl: Optional[int] = Field(
        title="Time to live in seconds (0 = no expiration)",
        default=0,
        ge=0,
        le=86400  # Max 24 hours
    )
