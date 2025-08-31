"""Notification apis."""

import logging
import os
from typing import Any

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from peewee import DoesNotExist
from py_vapid import Vapid01, utils

from frigate.api.defs.tags import Tags
from frigate.const import CONFIG_DIR
from frigate.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=[Tags.notifications])


@router.get("/notifications/pubkey")
def get_vapid_pub_key(request: Request):
    config = request.app.frigate_config
    notifications_enabled = config.notifications.enabled
    camera_notifications_enabled = [
        c for c in config.cameras.values() if c.enabled and c.notifications.enabled
    ]
    if not (notifications_enabled or camera_notifications_enabled):
        return JSONResponse(
            content=({"success": False, "message": "Notifications are not enabled."}),
            status_code=400,
        )

    key = Vapid01.from_file(os.path.join(CONFIG_DIR, "notifications.pem"))
    raw_pub = key.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return JSONResponse(content=utils.b64urlencode(raw_pub), status_code=200)


@router.post("/notifications/register")
def register_notifications(request: Request, body: dict = None):
    if request.app.frigate_config.auth.enabled:
        # FIXME: For FastAPI the remote-user is not being populated
        username = request.headers.get("remote-user") or "admin"
    else:
        username = "admin"

    json: dict[str, Any] = body or {}
    sub = json.get("sub")

    if not sub:
        return JSONResponse(
            content={"success": False, "message": "Subscription must be provided."},
            status_code=400,
        )

    try:
        User.update(notification_tokens=User.notification_tokens.append(sub)).where(
            User.username == username
        ).execute()
        return JSONResponse(
            content=({"success": True, "message": "Successfully saved token."}),
            status_code=200,
        )
    except DoesNotExist:
        return JSONResponse(
            content=({"success": False, "message": "Could not find user."}),
            status_code=404,
        )


@router.get("/notifications/weight-stats/{camera_name}")
def get_weight_statistics(request: Request, camera_name: str = Path(..., title="Camera name")):
    """Get notification weight statistics for a specific camera."""
    config = request.app.frigate_config
    dispatcher = request.app.dispatcher
    
    # Check if camera exists
    if camera_name not in config.cameras:
        raise HTTPException(status_code=404, detail=f"Camera {camera_name} not found")
    
    # Check if dispatcher and webpush client are available
    if not dispatcher or not dispatcher.web_push_client:
        raise HTTPException(status_code=503, detail="WebPush client not available")
    
    # Get weight statistics from WebPushClient
    try:
        stats = dispatcher.web_push_client.get_weight_statistics(camera_name)
        return JSONResponse(content=stats, status_code=200)
    except Exception as e:
        logger.error(f"Error getting weight statistics for {camera_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting weight statistics: {str(e)}")


@router.get("/notifications/weight-stats")
def get_all_weight_statistics(request: Request):
    """Get notification weight statistics for all cameras."""
    config = request.app.frigate_config
    dispatcher = request.app.dispatcher
    
    # Check if dispatcher and webpush client are available
    if not dispatcher or not dispatcher.web_push_client:
        raise HTTPException(status_code=503, detail="WebPush client not available")
    
    # Get weight statistics for all cameras
    try:
        all_stats = {}
        for camera_name in config.cameras.keys():
            if config.cameras[camera_name].enabled and config.cameras[camera_name].notifications.enabled:
                all_stats[camera_name] = dispatcher.web_push_client.get_weight_statistics(camera_name)
        
        return JSONResponse(content=all_stats, status_code=200)
    except Exception as e:
        logger.error(f"Error getting weight statistics for all cameras: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting weight statistics: {str(e)}")