import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import logging
import uuid

from sqlmodel import Session

from app.database import get_db
from app.websocket.hub import manager
from app.api.dependencies import get_current_user_ws
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/")
async def websocket_endpoint(
        websocket: WebSocket,
        token: str = Query(None),
):
    connection_id = str(uuid.uuid4())
    current_user = None
    db = None

    try:
        # PROPER database session management
        db = next(get_db())

        # Authenticate user if token provided
        if token:
            try:
                current_user = await get_current_user_ws(token, db)
            except Exception as auth_error:
                logger.warning(f"WebSocket auth failed: {auth_error}")
                await websocket.close(code=1008)  # Policy violation
                return

        await manager.connect(websocket, connection_id)

        if current_user:
            await manager.add_user_connection(str(current_user.id), connection_id)
            await manager.join_group(connection_id, f"user-{current_user.id}")

        # Heartbeat mechanism
        await websocket.send_json({"type": "heartbeat", "message": "connected"})

        while True:
            try:
                # Add timeout to prevent hanging connections
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0  # 30 second timeout
                )
                await handle_websocket_message(connection_id, data, current_user, db)
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except:
                    break  # Client disconnected
            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # GUARANTEED cleanup
        manager.disconnect(connection_id)
        if db:
            db.close()  # Explicitly close database connection


@router.get("/websocket/health")
async def websocket_health():
    return {
        "status": "healthy",
        "connections": len(manager.active_connections),
        "users": len(manager.user_connections)
    }

async def handle_websocket_message(connection_id: str, data: dict, current_user: User = None, db: Session = None):
    message_type = data.get("type")

    try:
        if message_type == "join_group":
            group_name = data.get("groupName")
            if group_name:
                await manager.join_group(connection_id, group_name)
                await manager.send_to_connection(connection_id, {
                    "type": "group_joined",
                    "groupName": group_name
                })

        elif message_type == "leave_group":
            group_name = data.get("groupName")
            if group_name:
                await manager.leave_group(connection_id, group_name)
                await manager.send_to_connection(connection_id, {
                    "type": "group_left",
                    "groupName": group_name
                })

        elif message_type == "join_notification_group":
            if current_user:
                await manager.join_group(connection_id, f"user-{current_user.id}")

        elif message_type == "leave_notification_group":
            if current_user:
                await manager.leave_group(connection_id, f"user-{current_user.id}")

        # Add any other message types that might need database access
        elif message_type == "some_db_operation" and db and current_user:
            # Perform database operations here
            pass

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        await manager.send_to_connection(connection_id, {
            "type": "error",
            "message": str(e)
        })