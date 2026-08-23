"""Notification apis."""

import ipaddress
import logging
import os
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from peewee import DoesNotExist
from py_vapid import Vapid01, utils

from frigate.api.auth import allow_any_authenticated, get_current_user,require_role
from frigate.api.defs.request.notification_body import SendNotificationBody
from frigate.api.defs.tags import Tags
from frigate.const import CONFIG_DIR
from frigate.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=[Tags.notifications])

# Push endpoints are opaque URLs but stay well under this in practice
MAX_ENDPOINT_LENGTH = 2048

# Suffixes that only ever resolve on the local network
INTERNAL_HOST_SUFFIXES = (".local", ".localdomain", ".internal", ".home.arpa")


def _validate_push_endpoint(endpoint: Any) -> str | None:
    """Return a reason the endpoint is unusable, or None when it is valid.

    Subscriptions are issued by the browser vendor's push service, so a valid
    endpoint is always a public https URL. Anything else is either a broken
    registration or an attempt to aim the notification sender somewhere it
    should not reach.
    """
    if not isinstance(endpoint, str) or not endpoint:
        return "endpoint must be a url"

    if len(endpoint) > MAX_ENDPOINT_LENGTH:
        return "endpoint is too long"

    try:
        parsed = urlparse(endpoint)
        port = parsed.port
    except ValueError:
        return "endpoint is not a valid url"

    if parsed.scheme != "https":
        return "endpoint must use https"

    if parsed.username or parsed.password:
        return "endpoint must not include credentials"

    if port is not None and port != 443:
        return "endpoint must use the default https port"

    hostname = parsed.hostname

    if not hostname:
        return "endpoint must include a hostname"

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None:
        # A push service is never reachable at an address only this network can
        # route, so anything non-global is a misconfiguration at best
        if not address.is_global:
            return "endpoint must not use a private address"
    elif hostname == "localhost" or "." not in hostname:
        return "endpoint must use a fully qualified hostname"
    elif hostname.endswith(INTERNAL_HOST_SUFFIXES):
        return "endpoint must not use an internal hostname"

    # The subscription token lives in the path, and webpush.py assumes there is
    # a separator after the host when it builds the VAPID audience
    if len(parsed.path) <= 1:
        return "endpoint must include a subscription path"

    return None


def _validate_subscription(sub: Any) -> str | None:
    """Return a reason the subscription is unusable, or None when it is valid."""
    if not isinstance(sub, dict):
        return "subscription must be an object"

    reason = _validate_push_endpoint(sub.get("endpoint"))

    if reason:
        return reason

    keys = sub.get("keys")

    if not isinstance(keys, dict):
        return "subscription must include keys"

    # WebPusher raises on a missing key, which would break every send for the
    # user rather than just this registration
    for name in ("p256dh", "auth"):
        value = keys.get(name)

        if not isinstance(value, str) or not value:
            return f"subscription keys must include {name}"

    return None


@router.get(
    "/notifications/pubkey",
    dependencies=[Depends(allow_any_authenticated())],
    summary="Get VAPID public key",
    description="""Gets the VAPID public key for the notifications.
    Returns the public key or an error if notifications are not enabled.
    """,
)
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


@router.post(
    "/notifications/register",
    dependencies=[Depends(allow_any_authenticated())],
    summary="Register notifications",
    description="""Registers a notifications subscription.
    Returns a success message or an error if the subscription is not provided.
    """,
)
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

    reason = _validate_subscription(sub)

    if reason:
        logger.warning(
            "Rejected notification registration for %s: %s", username, reason
        )
        return JSONResponse(
            content={"success": False, "message": f"Invalid subscription: {reason}"},
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
