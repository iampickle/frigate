from typing import Dict, Optional

from pydantic import BaseModel, Field


class CameraActionConfig(BaseModel):
    """Configuration for a single camera action."""
    
    name: str = Field(..., description="Display name for the action")
    url: str = Field(..., description="HTTP endpoint to call")
    method: str = Field(default="POST", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")
    body: Optional[str] = Field(default=None, description="Request body")
    icon: Optional[str] = Field(default=None, description="React icon name (e.g., 'FaLightbulb', 'FaBell')")
    standalone: bool = Field(default=False, description="Whether to display as standalone button instead of in dropdown")


class CameraActionsConfig(BaseModel):
    """Configuration for camera actions."""
    
    actions: list[CameraActionConfig] = Field(default_factory=list)
