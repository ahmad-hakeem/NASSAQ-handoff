"""
NASSAQ - Auth Service
Authentication and authorization utilities
"""
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List

from dependencies import JWT_SECRET, JWT_ALGORITHM

ACCESS_TOKEN_EXPIRE = 30

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_get_current_user(db):
    """Factory function to create get_current_user dependency with database access"""
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        try:
            payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            # Try to find by _id (ObjectId) first, then by id (UUID)
            from bson import ObjectId
            user = None
            try:
                user = await db.users.find_one({"_id": ObjectId(user_id)})
            except Exception:
                pass
            
            if not user:
                user = await db.users.find_one({"id": user_id})
            
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            # Convert _id to string id for consistency
            if "_id" in user:
                user["id"] = str(user["_id"])
                del user["_id"]
            
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    return get_current_user


def create_require_roles(UserRole):
    """Factory function to create role checker dependency"""
    def require_roles(allowed_roles: List):
        async def role_checker(current_user: dict = Depends(security)):
            if current_user["role"] not in [r.value for r in allowed_roles]:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return current_user
        return role_checker
    return require_roles


def require_roles_factory(allowed_roles, get_current_user):
    """Create a role requirement dependency"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        role_values = [r.value if hasattr(r, 'value') else r for r in allowed_roles]
        if current_user["role"] not in role_values:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker


def generate_temp_password(length: int = 12) -> str:
    """Generate a temporary password"""
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "@#$"
    return ''.join(secrets.choice(chars) for _ in range(length))
