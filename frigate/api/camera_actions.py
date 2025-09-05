"""Camera actions API."""
import logging
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/camera/{camera_name}/actions/{action_name}/trigger")
async def trigger_camera_action(
    request: Request, camera_name: str, action_name: str
) -> JSONResponse:
    """Trigger a specific camera action."""
    config = request.app.frigate_config
    
    if camera_name not in config.cameras:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera_config = config.cameras[camera_name]
    
    if not camera_config.actions or not camera_config.actions.actions:
        raise HTTPException(status_code=404, detail="No actions configured for camera")
    
    # Find the action
    action = None
    for a in camera_config.actions.actions:
        if a.name == action_name:
            action = a
            break
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            headers = action.headers or {}
            method = action.method or "POST"
            
            if method.upper() == "GET":
                async with session.get(action.url, headers=headers) as response:
                    response_text = await response.text()
                    status_ok = response.status < 400
            elif method.upper() == "POST":
                async with session.post(
                    action.url, headers=headers, data=action.body
                ) as response:
                    response_text = await response.text()
                    status_ok = response.status < 400
            else:
                async with session.request(
                    method, action.url, headers=headers, data=action.body
                ) as response:
                    response_text = await response.text()
                    status_ok = response.status < 400
                    
        if status_ok:
            logger.info(f"Successfully triggered action '{action_name}' for camera '{camera_name}'")
            return JSONResponse(
                content={"success": True, "message": f"Action '{action_name}' executed successfully"},
                status_code=200
            )
        else:
            logger.warning(f"Action '{action_name}' returned non-success status: {response.status}")
            return JSONResponse(
                content={"success": False, "message": f"Action returned status {response.status}"},
                status_code=200
            )
        
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error triggering action '{action_name}': {e}")
        return JSONResponse(
            content={"success": False, "message": f"Network error: {str(e)}"},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Failed to trigger action '{action_name}': {e}")
        return JSONResponse(
            content={"success": False, "message": f"Failed to trigger action: {str(e)}"},
            status_code=200
        )
