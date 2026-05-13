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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from dependencies import require_roles, UserRole

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
    async def websocket_notifications(websocket: WebSocket):
        """WebSocket endpoint للإشعارات الفورية"""
        
        await websocket.accept()

        auth_token = None
        client_gone = False
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            msg = json.loads(raw)
            if msg.get("type") == "auth":
                auth_token = msg.get("token")
        except WebSocketDisconnect:
            # Client closed before sending auth message — nothing more to do.
            client_gone = True
        except asyncio.TimeoutError:
            # Auth message never arrived in time.
            pass
        except json.JSONDecodeError:
            # Malformed auth payload.
            pass
        except Exception as e:
            logger.debug(f"WebSocket auth-receive failed: {e}")

        if client_gone:
            return

        if not auth_token:
            try:
                await websocket.send_json({"type": "error", "message": "Token required"})
            except Exception:
                pass
            try:
                await websocket.close(code=4001, reason="Token required")
            except Exception:
                pass
            return
        
        try:
            payload = await decode_token(auth_token)
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

            # Task #288 — IT perimeter "finish setup" parity for live updates.
            # Mirror the HTTP `require_workspace_materialised` gate at the
            # WebSocket handshake: an Independent-Teacher token whose
            # workspace has not been bootstrapped yet (no `tenant_id` claim)
            # would otherwise silently fail any tenant-scoped broadcast.
            # Close with a dedicated code (4003) + canonical reason so the
            # frontend can route the user to the same one-shot wizard
            # dialog as the HTTP path. Other roles are unaffected.
            if role == "independent_teacher" and not tenant_id:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "code": "WORKSPACE_NOT_MATERIALISED",
                        "message": "يجب إكمال إنشاء مساحتك أولًا.",
                    })
                except Exception:
                    pass
                try:
                    await websocket.close(code=4003, reason="workspace not materialised")
                except Exception:
                    pass
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
            
            # Capture the access-token jti so the ping loop can revalidate
            # it against revoked_tokens and force-close in-flight sockets
            # whose token was logged out / revoked elsewhere
            # (audit Open Question 3).
            _conn_jti = payload.get("jti")

            async def _server_ping_loop(ws, uid, conn_jti):
                """Server-initiated ping every 30s + revocation check.
                Force-closes the socket on send failure OR when the JWT jti
                that authenticated the connection has been revoked."""
                try:
                    while True:
                        await asyncio.sleep(30)
                        # Phase 3 — in-flight revocation propagation.
                        if conn_jti:
                            try:
                                from db import async_session_factory as _asf
                                async with _asf() as _ws_check:
                                    revoked = await gd_find_one(
                                        _ws_check, "revoked_tokens", {"jti": conn_jti}
                                    )
                                if revoked:
                                    logger.info(
                                        f"WS jti={conn_jti} revoked — closing socket for user={uid}"
                                    )
                                    try:
                                        await ws.close(code=4001, reason="token revoked")
                                    except Exception:
                                        pass
                                    return
                            except Exception as _rv:
                                logger.debug(f"WS revocation check failed: {_rv}")
                        try:
                            await ws.send_json({"type": "server_ping", "ts": datetime.now(timezone.utc).isoformat()})
                        except Exception:
                            logger.info(f"Server ping failed for user={uid}, force-closing")
                            try:
                                await ws.close(code=4002, reason="ping failed")
                            except Exception:
                                pass
                            return
                except asyncio.CancelledError:
                    pass

            ping_task = asyncio.create_task(_server_ping_loop(websocket, user_id, _conn_jti))
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
                                async with async_session_factory() as ws_session:
                                    await gd_update_one(ws_session, "notifications",
                                        {"id": notification_id, "user_id": user_id},
                                        {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}
                                    )
                                    await ws_session.commit()
                    except json.JSONDecodeError:
                        logger.debug(f"Malformed JSON from WebSocket user={user_id}")
                        
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
    async def get_websocket_stats(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
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
    
    def _build_db_row(uid: str) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "tenant_id": target_tenant,
            "title": type_config["title_ar"],
            "message": message_ar,
            "type": notification_type,
            "priority": type_config["priority"],
            "is_read": False,
            "extra_data": {
                "title_en": type_config["title_en"],
                "message_en": message_en,
                "icon": type_config["icon"],
                "sound": type_config["sound"],
                **(extra_data or {}),
            },
        }

    # Send to targets
    if broadcast_all:
        await manager.broadcast_to_all(notification)
        if save_to_db:
            users = await gd_find(db.session, "users", {"is_active": True}, limit=10000)
            for user in users:
                await gd_insert(db.session, "notifications", _build_db_row(user["id"]))
    
    elif target_users:
        for user_id in target_users:
            await manager.send_personal_message(notification, user_id)
            if save_to_db:
                await gd_insert(db.session, "notifications", _build_db_row(user_id))
    
    elif target_roles:
        await manager.broadcast_to_roles(notification, target_roles)
        if save_to_db:
            for role in target_roles:
                users = await gd_find(db.session, "users", {"role": role, "is_active": True}, limit=1000)
                for user in users:
                    await gd_insert(db.session, "notifications", _build_db_row(user["id"]))
    
    elif target_tenant:
        await manager.broadcast_to_tenant(notification, target_tenant)
        if save_to_db:
            users = await gd_find(db.session, "users", {"tenant_id": target_tenant, "is_active": True}, limit=1000)
            for user in users:
                await gd_insert(db.session, "notifications", _build_db_row(user["id"]))
    
    return notification_id
