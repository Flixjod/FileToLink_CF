from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, mongo_uri: str, database_name: str):
        self.client = AsyncIOMotorClient(
            mongo_uri,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
        )
        self.db         = self.client[database_name]
        self.files      = self.db.files
        self.users      = self.db.users
        self.bandwidth  = self.db.bandwidth
        self.sudo_users = self.db.sudo_users
        self.config     = self.db.config

    async def init_db(self):
        try:
            await self.files.create_index("file_id",    unique=True)
            await self.files.create_index("message_id", unique=True)
            await self.files.create_index("user_id")
            await self.files.create_index("created_at")
            await self.users.create_index("user_id",        unique=True)
            await self.users.create_index("last_activity")
            await self.bandwidth.create_index("date")
            await self.sudo_users.create_index("user_id",   unique=True)
            logger.info("database indexes created")
            return True
        except Exception as e:
            logger.error("database init error: %s", e)
            return False

    async def add_file(self, file_data: Dict) -> bool:
        try:
            doc = {
                "file_id":          file_data["file_id"],
                "message_id":       file_data["message_id"],
                "telegram_file_id": file_data.get("telegram_file_id", ""),
                "user_id":          file_data["user_id"],
                "username":         file_data.get("username", ""),
                "file_name":        file_data["file_name"],
                "file_size":        file_data["file_size"],
                "file_type":        file_data["file_type"],
                "mime_type":        file_data.get("mime_type", ""),
                "created_at":       datetime.utcnow(),
                "downloads":        0,
                "bandwidth_used":   0,
            }
            await self.files.insert_one(doc)
            return True
        except Exception as e:
            logger.error("add file error: %s", e)
            return False

    async def get_file(self, message_id: str) -> Optional[Dict]:
        try:
            return await self.files.find_one({"message_id": message_id})
        except Exception as e:
            logger.error("get file error: %s", e)
            return None

    async def get_file_by_hash(self, file_hash: str) -> Optional[Dict]:
        try:
            return await self.files.find_one({"file_id": file_hash})
        except Exception as e:
            logger.error("get file by hash error: %s", e)
            return None

    async def delete_file(self, message_id: str) -> bool:
        try:
            result = await self.files.delete_one({"message_id": message_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("delete file error: %s", e)
            return False

    async def delete_all_files(self) -> int:
        try:
            result = await self.files.delete_many({})
            return result.deleted_count
        except Exception as e:
            logger.error("delete all files error: %s", e)
            return 0

    async def get_user_files(self, user_id: str, limit: int = 50) -> List[Dict]:
        try:
            cursor = self.files.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error("get user files error: %s", e)
            return []

    async def increment_downloads(self, message_id: str, size: int = 0) -> bool:
        try:
            await self.files.update_one(
                {"message_id": message_id},
                {"$inc": {"downloads": 1, "bandwidth_used": size}},
            )
            await self.update_bandwidth(size)
            return True
        except Exception as e:
            logger.error("increment downloads error: %s", e)
            return False

    async def register_user(self, user_data: Dict) -> bool:
        try:
            await self.users.update_one(
                {"user_id": user_data["user_id"]},
                {
                    "$setOnInsert": {"first_used": datetime.utcnow()},
                    "$set": {
                        "username":      user_data.get("username", ""),
                        "first_name":    user_data.get("first_name", ""),
                        "last_name":     user_data.get("last_name", ""),
                        "last_activity": datetime.utcnow(),
                    },
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error("register user error: %s", e)
            return False

    async def register_user_on_start(self, user_data: Dict) -> bool:
        try:
            existing = await self.users.find_one({"user_id": user_data["user_id"]})
            if existing:
                # User already registered — just update last_activity silently
                await self.users.update_one(
                    {"user_id": user_data["user_id"]},
                    {"$set": {"last_activity": datetime.utcnow()}},
                )
                return True  # already exists, nothing to register

            # New user — insert full record
            await self.users.insert_one({
                "user_id":       user_data["user_id"],
                "username":      user_data.get("username", ""),
                "first_name":    user_data.get("first_name", ""),
                "last_name":     user_data.get("last_name", ""),
                "first_used":    datetime.utcnow(),
                "last_activity": datetime.utcnow(),
            })
            logger.info("new user registered: %s", user_data["user_id"])
            return True
        except Exception as e:
            logger.error("register_user_on_start error: %s", e)
            return False

    async def get_user(self, user_id: str) -> Optional[Dict]:
        try:
            return await self.users.find_one({"user_id": user_id})
        except Exception as e:
            logger.error("get user error: %s", e)
            return None

    async def update_bandwidth(self, size: int) -> bool:
        try:
            today = datetime.utcnow().date().isoformat()
            await self.bandwidth.update_one(
                {"date": today},
                {
                    "$inc": {"total_bytes": size, "total_downloads": 1},
                    "$set": {"last_updated": datetime.utcnow()},
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error("update bandwidth error: %s", e)
            return False

    async def get_total_bandwidth(self) -> int:
        try:
            pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_bytes"}}}]
            result   = await self.bandwidth.aggregate(pipeline).to_list(length=1)
            return result[0]["total"] if result else 0
        except Exception as e:
            logger.error("get total bandwidth error: %s", e)
            return 0

    async def get_bandwidth_stats(self) -> Dict:
        try:
            total       = await self.get_total_bandwidth()
            today       = datetime.utcnow().date().isoformat()
            today_stats = await self.bandwidth.find_one({"date": today})
            return {
                "total_bandwidth": total,
                "today_bandwidth": today_stats.get("total_bytes", 0)    if today_stats else 0,
                "today_downloads": today_stats.get("total_downloads", 0) if today_stats else 0,
            }
        except Exception as e:
            logger.error("get bandwidth stats error: %s", e)
            return {"total_bandwidth": 0, "today_bandwidth": 0, "today_downloads": 0}

    async def get_stats(self) -> Dict:
        try:
            total_files = await self.files.count_documents({})
            total_users = await self.users.count_documents({})
            pipeline    = [{"$group": {"_id": None, "total": {"$sum": "$downloads"}}}]
            dl_result   = await self.files.aggregate(pipeline).to_list(length=1)
            total_dl    = dl_result[0]["total"] if dl_result else 0
            bw          = await self.get_bandwidth_stats()
            return {
                "total_files":     total_files,
                "total_users":     total_users,
                "total_downloads": total_dl,
                "total_bandwidth": bw["total_bandwidth"],
                "today_bandwidth": bw["today_bandwidth"],
                "today_downloads": bw["today_downloads"],
            }
        except Exception as e:
            logger.error("get stats error: %s", e)
            return {
                "total_files": 0, "total_users": 0, "total_downloads": 0,
                "total_bandwidth": 0, "today_bandwidth": 0, "today_downloads": 0,
            }

    async def add_sudo_user(self, user_id: str, added_by: str) -> bool:
        try:
            await self.sudo_users.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "added_by": added_by, "added_at": datetime.utcnow()}},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error("add sudo user error: %s", e)
            return False

    async def remove_sudo_user(self, user_id: str) -> bool:
        try:
            result = await self.sudo_users.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("remove sudo user error: %s", e)
            return False

    async def is_sudo_user(self, user_id: str) -> bool:
        try:
            result = await self.sudo_users.find_one({"user_id": user_id})
            return result is not None
        except Exception as e:
            logger.error("is sudo user error: %s", e)
            return False

    async def get_sudo_users(self) -> List[Dict]:
        try:
            cursor = self.sudo_users.find({})
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error("get sudo users error: %s", e)
            return []

    async def close(self):
        self.client.close()
