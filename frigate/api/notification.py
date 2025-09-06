"""Notification apis."""

import logging
import os
from typing import Any

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from peewee import DoesNotExist
from py_vapid import Vapid01, utils

from frigate.api.auth import get_current_user, require_role
from frigate.api.defs.request.notification_body import SendNotificationBody
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


@router.post("/notifications/send", dependencies=[Depends(require_role(["admin"]))])
@router.get("/notifications/send", dependencies=[Depends(require_role(["admin"]))])
async def send_custom_notification(
    request: Request,
    current_user: dict = Depends(get_current_user),
    body: SendNotificationBody = None,
    title: str = Query(None, description="Notification title (max 200 characters)"),
    message: str = Query(None, description="Notification message (max 500 characters)"),
    direct_url: str = Query("", description="URL to open when notification is clicked"),
    image: str = Query("", description="Image URL to display in notification"),
    ttl: int = Query(0, ge=0, le=86400, description="Time to live in seconds (0 = no expiration)"),
):
    """Send a custom notification to all registered users.
    
    Parameters can be passed either in the request body (POST) or as query parameters (GET/POST).
    Query parameters take precedence over body parameters.
    
    Examples:
    GET  /api/notifications/send?title=Hello&message=World
    POST /api/notifications/send?title=Hello&message=World
    POST /api/notifications/send (with JSON body)
    """
    if isinstance(current_user, JSONResponse):
        return current_user

    # Get parameters from query string or body
    # Query parameters take precedence
    notification_title = title or (body.title if body else None)
    notification_message = message or (body.message if body else None)
    notification_direct_url = direct_url or (body.direct_url if body else "")
    notification_image = image or (body.image if body else "")
    notification_ttl = ttl or (body.ttl if body else 0)

    # Validate required parameters
    if not notification_title:
        return JSONResponse(
            content=({"success": False, "message": "Title is required."}),
            status_code=400,
        )
    
    if not notification_message:
        return JSONResponse(
            content=({"success": False, "message": "Message is required."}),
            status_code=400,
        )

    # Validate parameter lengths and values
    if len(notification_title) > 200:
        return JSONResponse(
            content=({"success": False, "message": "Title too long (max 200 characters)."}),
            status_code=400,
        )
    
    if len(notification_message) > 500:
        return JSONResponse(
            content=({"success": False, "message": "Message too long (max 500 characters)."}),
            status_code=400,
        )
    
    if notification_ttl < 0 or notification_ttl > 86400:
        return JSONResponse(
            content=({"success": False, "message": "TTL must be between 0 and 86400 seconds."}),
            status_code=400,
        )

    config = request.app.frigate_config
    dispatcher = request.app.dispatcher

    # Check if notifications are enabled globally or for any camera
    notifications_enabled = config.notifications.enabled
    camera_notifications_enabled = [
        c for c in config.cameras.values() if c.enabled and c.notifications.enabled
    ]
    
    if not (notifications_enabled or camera_notifications_enabled):
        return JSONResponse(
            content=({"success": False, "message": "Notifications are not enabled."}),
            status_code=400,
        )

    # Check if dispatcher and webpush client are available
    if not dispatcher or not dispatcher.web_push_client:
        return JSONResponse(
            content=({"success": False, "message": "WebPush client not available."}),
            status_code=503,
        )

    try:
        # Send notification to all registered users
        web_push_client = dispatcher.web_push_client
        web_push_client.check_registrations()

        if not web_push_client.web_pushers:
            return JSONResponse(
                content=({"success": False, "message": "No users registered for notifications."}),
                status_code=400,
            )

        # Send to all registered users
        for user in web_push_client.web_pushers:
            web_push_client.send_push_notification(
                user=user,
                payload={"type": "custom", "sender": current_user["username"]},
                title=notification_title,
                message=notification_message,
                direct_url=notification_direct_url or "/",
                image=notification_image or "",
                notification_type="custom",
                ttl=notification_ttl,
            )

        user_count = len(web_push_client.web_pushers)
        return JSONResponse(
            content=({"success": True, "message": f"Notification sent to {user_count} user(s)."}),
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Error sending custom notification: {e}")
        return JSONResponse(
            content=({"success": False, "message": f"Error sending notification: {str(e)}"}),
            status_code=500,
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