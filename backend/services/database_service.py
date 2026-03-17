"""
NASSAQ - Database Service
Database connection and utilities
"""
from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import Optional

# MongoDB connection singleton
_client: Optional[AsyncIOMotorClient] = None
_db = None


def get_database():
    """Get the database instance"""
    global _client, _db
    
    if _db is None:
        mongo_url = os.environ['MONGO_URL']
        db_name = os.environ['DB_NAME']
        _client = AsyncIOMotorClient(mongo_url)
        _db = _client[db_name]
    
    return _db


def get_client():
    """Get the MongoDB client"""
    global _client
    
    if _client is None:
        mongo_url = os.environ['MONGO_URL']
        _client = AsyncIOMotorClient(mongo_url)
    
    return _client


async def close_database():
    """Close database connection"""
    global _client
    if _client:
        _client.close()
        _client = None


def serialize_doc(doc: dict) -> dict:
    """Serialize a MongoDB document for JSON response"""
    if doc is None:
        return None
    
    result = dict(doc)
    
    # Convert ObjectId to string
    if "_id" in result:
        result["id"] = str(result["_id"])
        del result["_id"]
    
    return result


def serialize_docs(docs: list) -> list:
    """Serialize a list of MongoDB documents"""
    return [serialize_doc(doc) for doc in docs if doc]


async def create_indexes(db):
    """Create database indexes for better performance"""
    # Users collection indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index("tenant_id")
    await db.users.create_index("role")
    
    # Schools collection indexes
    await db.schools.create_index("id", unique=True)
    await db.schools.create_index("code", unique=True)
    await db.schools.create_index("status")
    
    # Students collection indexes
    await db.students.create_index("id", unique=True)
    await db.students.create_index("school_id")
    await db.students.create_index("class_id")
    await db.students.create_index("student_number")
    
    # Teachers collection indexes
    await db.teachers.create_index("id", unique=True)
    await db.teachers.create_index("school_id")
    await db.teachers.create_index("email")
    
    # Classes collection indexes
    await db.classes.create_index("id", unique=True)
    await db.classes.create_index("school_id")
    
    # Attendance collection indexes
    await db.attendance.create_index([("student_id", 1), ("date", 1)])
    await db.attendance.create_index("class_id")
    await db.attendance.create_index("school_id")
    
    # Schedule sessions indexes
    await db.schedule_sessions.create_index("school_id")
    await db.schedule_sessions.create_index("teacher_id")
    await db.schedule_sessions.create_index("class_id")
    
    # Audit logs indexes
    await db.audit_logs.create_index("timestamp")
    await db.audit_logs.create_index("action")
    await db.audit_logs.create_index("action_by")
