from motor.motor_asyncio import AsyncIOMotorDatabase

from .db import get_db


def db_dep() -> AsyncIOMotorDatabase:
    return get_db()
