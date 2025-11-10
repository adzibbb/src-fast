import logging
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import uuid
from app.database import get_db
from app.api.dependencies import get_current_user_ws
from app.models.user import User

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_groups: Dict[str, List[str]] = {}
        self.user_connections: Dict[str, List[str]] = {}
        self.max_connections_per_user = 5  # Prevent abuse

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"Connection {connection_id} established")

    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # Remove from groups
        for group_name, connections in self.user_groups.items():
            if connection_id in connections:
                connections.remove(connection_id)

        # Remove from user connections
        for user_id, connections in self.user_connections.items():
            if connection_id in connections:
                connections.remove(connection_id)

        logger.info(f"Connection {connection_id} disconnected")

    async def join_group(self, connection_id: str, group_name: str):
        if group_name not in self.user_groups:
            self.user_groups[group_name] = []

        if connection_id not in self.user_groups[group_name]:
            self.user_groups[group_name].append(connection_id)
            logger.info(f"Connection {connection_id} joined group {group_name}")

    async def leave_group(self, connection_id: str, group_name: str):
        if group_name in self.user_groups and connection_id in self.user_groups[group_name]:
            self.user_groups[group_name].remove(connection_id)
            logger.info(f"Connection {connection_id} left group {group_name}")

    async def add_user_connection(self, user_id: str, connection_id: str):
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []

        # Enforce connection limits
        if len(self.user_connections[user_id]) >= self.max_connections_per_user:
            # Close oldest connection
            oldest_conn = self.user_connections[user_id].pop(0)
            await self.close_connection(oldest_conn)

        if connection_id not in self.user_connections[user_id]:
            self.user_connections[user_id].append(connection_id)
            logger.info(f"User {user_id} added connection {connection_id}")

    async def send_to_connection(self, connection_id: str, message: dict):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)

    async def send_to_group(self, group_name: str, message: dict):
        if group_name in self.user_groups:
            for connection_id in self.user_groups[group_name]:
                await self.send_to_connection(connection_id, message)

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                await self.send_to_connection(connection_id, message)

    async def broadcast(self, message: dict):
        for connection_id in self.active_connections:
            await self.send_to_connection(connection_id, message)

    async def send_notification_to_user(self, user_id: str, notification: dict):
        """Send notification to specific user"""
        await self.send_to_user(user_id, {
            "type": "receive_notification",
            "notification": notification
        })

    async def send_post_update_to_group(self, group_name: str, post_id: str):
        """Notify group about post update"""
        await self.send_to_group(group_name, {
            "type": "receive_post_update",
            "postId": post_id
        })

    async def broadcast_leaderboard_update(self):
        """Notify all clients about leaderboard changes"""
        await self.broadcast({
            "type": "receive_leaderboard_update"
        })

    async def close_connection(self, connection_id: str):
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].close()
            except:
                pass
            self.disconnect(connection_id)

    def get_connection_stats(self) -> dict:
        return {
            "total_connections": len(self.active_connections),
            "total_users": len(self.user_connections),
            "total_groups": len(self.user_groups),
            "connections_per_user": {
                user_id: len(conns)
                for user_id, conns in self.user_connections.items()
            }
        }

# Global connection manager
manager = ConnectionManager()