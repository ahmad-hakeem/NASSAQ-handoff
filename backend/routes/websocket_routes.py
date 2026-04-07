"""
NASSAQ - WebSocket Routes for Real-time Notifications
إشعارات فورية عبر WebSocket
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone
import json
import asyncio
import uuid
import logging

logger = logging.getLogger("nassaq.websocket")


class ConnectionManager:
    """إدارة اتصالات WebSocket"""
    
    def __init__(self):
        # user_id -> list of websocket connections (user can have multiple tabs)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # role -> set of user_ids (for broadcasting to specific roles)
        self.role_connections: Dict[str, Set[str]] = {}
        # tenant_id -> set of user_ids (for school-specific broadcasts)
        self.tenant_connections: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, role: str, tenant_id: Optional[str] = None):
        """إضافة اتصال جديد"""
        await websocket.accept()
        
        # Add to user connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # Add to role connections
        if role not in self.role_connections:
            self.role_connections[role] = set()
        self.role_connections[role].add(user_id)
        
        # Add to tenant connections
        if tenant_id:
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(user_id)
        
        logger.info(f"WebSocket connected: user={user_id}, role={role}")
        logger.info(f"Active WS connections: {len(self.active_connections)} users")
    
    def disconnect(self, websocket: WebSocket, user_id: str, role: str, tenant_id: Optional[str] = None):
        """إزالة اتصال"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # Remove user if no more connections
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
                # Remove from role connections
                if role in self.role_connections and user_id in self.role_connections[role]:
                    self.role_connections[role].discard(user_id)
                
                # Remove from tenant connections
                if tenant_id and tenant_id in self.tenant_connections:
                    self.tenant_connections[tenant_id].discard(user_id)
        
        logger.info(f"WebSocket disconnected: user={user_id}")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """إرسال رسالة لمستخدم محدد"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"WS send error for {user_id}: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                if conn in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(conn)
    
    async def broadcast_to_role(self, message: dict, role: str):
        """بث رسالة لجميع مستخدمي دور معين"""
        if role in self.role_connections:
            for user_id in self.role_connections[role].copy():
                await self.send_personal_message(message, user_id)
    
    async def broadcast_to_roles(self, message: dict, roles: List[str]):
        """بث رسالة لعدة أدوار"""
        for role in roles:
            await self.broadcast_to_role(message, role)
    
    async def broadcast_to_tenant(self, message: dict, tenant_id: str):
        """بث رسالة لجميع مستخدمي مدرسة معينة"""
        if tenant_id in self.tenant_connections:
            for user_id in self.tenant_connections[tenant_id].copy():
                await self.send_personal_message(message, user_id)
    
    async def broadcast_to_all(self, message: dict):
        """بث رسالة للجميع"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)
    
    def get_online_users_count(self) -> int:
        """عدد المستخدمين المتصلين"""
        return len(self.active_connections)
    
    def get_online_users_by_role(self, role: str) -> int:
        """عدد المستخدمين المتصلين من دور معين"""
        return len(self.role_connections.get(role, set()))
    
    def is_user_online(self, user_id: str) -> bool:
        """هل المستخدم متصل؟"""
        return user_id in self.active_connections


# Global connection manager
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager"""
    return manager


def create_websocket_routes(db, decode_token):
    """Create WebSocket routes"""
    
    router = APIRouter(tags=["WebSocket"])
    
    @router.websocket("/ws/notifications")
    async def websocket_notifications(websocket: WebSocket, token: str = None):
        """WebSocket endpoint للإشعارات الفورية"""
        
        # First accept the connection
        await websocket.accept()
        
        if not token:
            await websocket.send_json({"type": "error", "message": "Token required"})
            await websocket.close(code=4001, reason="Token required")
            return
        
        try:
            # Decode and validate token
            payload = decode_token(token)
            if not payload:
                await websocket.send_json({"type": "error", "message": "Invalid token"})
                await websocket.close(code=4001, reason="Invalid token")
                return
            
            user_id = payload.get("sub")
            role = payload.get("role")
            tenant_id = payload.get("tenant_id")
            
            if not user_id or not role:
                await websocket.send_json({"type": "error", "message": "Invalid token payload"})
                await websocket.close(code=4001, reason="Invalid token payload")
                return
            
            # Register connection
            if user_id not in manager.active_connections:
                manager.active_connections[user_id] = []
            manager.active_connections[user_id].append(websocket)
            
            # Add to role connections
            if role not in manager.role_connections:
                manager.role_connections[role] = set()
            manager.role_connections[role].add(user_id)
            
            # Add to tenant connections
            if tenant_id:
                if tenant_id not in manager.tenant_connections:
                    manager.tenant_connections[tenant_id] = set()
                manager.tenant_connections[tenant_id].add(user_id)
            
            logger.info(f"WebSocket connected: user={user_id}")
            
            # Send welcome message
            await websocket.send_json({
                "type": "connection_established",
                "message": "مرحباً! تم الاتصال بنجاح",
                "user_id": user_id,
                "online_users": manager.get_online_users_count()
            })
            
            async def _server_ping_loop(ws, uid):
                """Server-initiated ping every 30s; force-closes socket on failure."""
                try:
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send_json({"type": "server_ping", "ts": datetime.now(timezone.utc).isoformat()})
                        except Exception:
                            logger.info(f"Server ping failed for user={uid}, force-closing")
                            try:
                                await ws.close(code=4001, reason="ping failed")
                            except Exception:
                                pass
                            return
                except asyncio.CancelledError:
                    pass

            ping_task = asyncio.create_task(_server_ping_loop(websocket, user_id))
            try:
                while True:
                    data = await websocket.receive_text()
                    
                    try:
                        message = json.loads(data)
                        
                        if message.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                        
                        elif message.get("type") == "mark_read":
                            notification_id = message.get("notification_id")
                            if notification_id:
                                from db import async_session_factory
                                from repositories import Repos
                                async with async_session_factory() as ws_session:
                                    ws_repos = Repos(ws_session)
                                    await ws_repos.notifications.update_one(
                                        {"id": notification_id, "recipient_id": user_id},
                                        {"$set": {"read_status": True, "read_at": datetime.now(timezone.utc).isoformat()}}
                                    )
                                    await ws_session.commit()
                    except json.JSONDecodeError:
                        pass
                        
            except (WebSocketDisconnect, Exception) as e:
                if not isinstance(e, WebSocketDisconnect):
                    logger.warning(f"WebSocket error: {e}")
            finally:
                ping_task.cancel()
                manager.disconnect(websocket, user_id, role, tenant_id)
                
        except Exception as e:
            logger.warning(f"WebSocket connection error: {e}")
            try:
                await websocket.close(code=4000, reason="internal error")
            except Exception as e:
                logger.debug(f"Failed to close WebSocket gracefully: {e}")
    
    @router.get("/ws/stats")
    async def get_websocket_stats():
        """إحصائيات الاتصالات"""
        return {
            "online_users": manager.get_online_users_count(),
            "platform_admins_online": manager.get_online_users_by_role("platform_admin"),
            "school_principals_online": manager.get_online_users_by_role("school_principal"),
            "teachers_online": manager.get_online_users_by_role("teacher"),
        }
    
    return router, manager


# Notification types with Arabic/English messages
NOTIFICATION_TYPES = {
    "teacher_request": {
        "title_ar": "طلب تسجيل معلم جديد",
        "title_en": "New Teacher Registration Request",
        "icon": "user-plus",
        "sound": True,
        "priority": "high"
    },
    "security_alert": {
        "title_ar": "تنبيه أمني",
        "title_en": "Security Alert",
        "icon": "shield-alert",
        "sound": True,
        "priority": "critical"
    },
    "broadcast_message": {
        "title_ar": "رسالة جديدة",
        "title_en": "New Message",
        "icon": "megaphone",
        "sound": True,
        "priority": "medium"
    },
    "system_alert": {
        "title_ar": "تنبيه النظام",
        "title_en": "System Alert",
        "icon": "alert-triangle",
        "sound": True,
        "priority": "high"
    },
    "maintenance_mode": {
        "title_ar": "وضع الصيانة",
        "title_en": "Maintenance Mode",
        "icon": "wrench",
        "sound": True,
        "priority": "critical"
    },
    "login_attempt": {
        "title_ar": "محاولة تسجيل دخول",
        "title_en": "Login Attempt",
        "icon": "log-in",
        "sound": False,
        "priority": "low"
    },
    "account_locked": {
        "title_ar": "تم قفل الحساب",
        "title_en": "Account Locked",
        "icon": "lock",
        "sound": True,
        "priority": "high"
    }
}


async def send_realtime_notification(
    manager: ConnectionManager,
    db,
    notification_type: str,
    message_ar: str,
    message_en: str,
    target_users: List[str] = None,
    target_roles: List[str] = None,
    target_tenant: str = None,
    broadcast_all: bool = False,
    extra_data: dict = None,
    save_to_db: bool = True
):
    """
    إرسال إشعار فوري
    
    Args:
        manager: Connection manager
        db: Database connection
        notification_type: نوع الإشعار
        message_ar: الرسالة بالعربية
        message_en: الرسالة بالإنجليزية
        target_users: قائمة معرفات المستخدمين المستهدفين
        target_roles: قائمة الأدوار المستهدفة
        target_tenant: معرف المدرسة المستهدفة
        broadcast_all: بث للجميع
        extra_data: بيانات إضافية
        save_to_db: حفظ في قاعدة البيانات
    """
    
    type_config = NOTIFICATION_TYPES.get(notification_type, {
        "title_ar": "إشعار",
        "title_en": "Notification",
        "icon": "bell",
        "sound": True,
        "priority": "medium"
    })
    
    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    notification = {
        "id": notification_id,
        "type": "realtime_notification",
        "notification_type": notification_type,
        "title_ar": type_config["title_ar"],
        "title_en": type_config["title_en"],
        "message_ar": message_ar,
        "message_en": message_en,
        "icon": type_config["icon"],
        "sound": type_config["sound"],
        "priority": type_config["priority"],
        "created_at": now,
        "read_status": False,
        **(extra_data or {})
    }
    
    # Send to targets
    if broadcast_all:
        await manager.broadcast_to_all(notification)
        
        # Save to all users in DB
        if save_to_db:
            users = await db.users.find({"is_active": True}, {"id": 1}).to_list(10000)
            for user in users:
                await db.notifications.insert_one({
                    **notification,
                    "id": str(uuid.uuid4()),
                    "recipient_id": user["id"]
                })
    
    elif target_users:
        for user_id in target_users:
            await manager.send_personal_message(notification, user_id)
            
            if save_to_db:
                await db.notifications.insert_one({
                    **notification,
                    "recipient_id": user_id
                })
    
    elif target_roles:
        await manager.broadcast_to_roles(notification, target_roles)
        
        if save_to_db:
            for role in target_roles:
                users = await db.users.find({"role": role, "is_active": True}, {"id": 1}).to_list(1000)
                for user in users:
                    await db.notifications.insert_one({
                        **notification,
                        "id": str(uuid.uuid4()),
                        "recipient_id": user["id"]
                    })
    
    elif target_tenant:
        await manager.broadcast_to_tenant(notification, target_tenant)
        
        if save_to_db:
            users = await db.users.find({"tenant_id": target_tenant, "is_active": True}, {"id": 1}).to_list(1000)
            for user in users:
                await db.notifications.insert_one({
                    **notification,
                    "id": str(uuid.uuid4()),
                    "recipient_id": user["id"]
                })
    
    return notification_id
