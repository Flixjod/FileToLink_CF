from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, mongo_uri: str, database_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[database_name]
        
        # Collections
        self.files = self.db.files
        self.users = self.db.users
        self.bandwidth = self.db.bandwidth
        self.sudo_users = self.db.sudo_users
        
    async def init_db(self):
        """Initialize database indexes"""
        try:
            # Files collection indexes
            await self.files.create_index("file_id", unique=True)
            await self.files.create_index("message_id", unique=True)
            await self.files.create_index("user_id")
            await self.files.create_index("secret_token", unique=True)
            await self.files.create_index("created_at")
            
            # Users collection indexes
            await self.users.create_index("user_id", unique=True)
            await self.users.create_index("last_activity")
            
            # Bandwidth collection indexes
            await self.bandwidth.create_index("date")
            
            # Sudo users collection indexes
            await self.sudo_users.create_index("user_id", unique=True)
            
            logger.info("Database indexes created successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            return False
    
    # ==================== FILE OPERATIONS ====================
    
    async def add_file(self, file_data: Dict) -> bool:
        """Add a new file to database"""
        try:
            file_doc = {
                "file_id": file_data["file_id"],
                "message_id": file_data["message_id"],
                "user_id": file_data["user_id"],
                "username": file_data.get("username", ""),
                "file_name": file_data["file_name"],
                "file_size": file_data["file_size"],
                "file_type": file_data["file_type"],
                "secret_token": file_data["secret_token"],
                "created_at": datetime.utcnow(),
                "downloads": 0,
                "bandwidth_used": 0
            }
            await self.files.insert_one(file_doc)
            return True
        except Exception as e:
            logger.error(f"Add file error: {e}")
            return False
    
    async def get_file(self, message_id: str) -> Optional[Dict]:
        """Get file by message ID"""
        try:
            return await self.files.find_one({"message_id": message_id})
        except Exception as e:
            logger.error(f"Get file error: {e}")
            return None
    
    async def get_file_by_token(self, token: str) -> Optional[Dict]:
        """Get file by secret token"""
        try:
            return await self.files.find_one({"secret_token": token})
        except Exception as e:
            logger.error(f"Get file by token error: {e}")
            return None
    
    async def delete_file(self, message_id: str) -> bool:
        """Delete file from database"""
        try:
            result = await self.files.delete_one({"message_id": message_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Delete file error: {e}")
            return False
    
    async def delete_all_files(self) -> int:
        """Delete all files from database"""
        try:
            result = await self.files.delete_many({})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Delete all files error: {e}")
            return 0
    
    async def get_user_files(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's files"""
        try:
            cursor = self.files.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Get user files error: {e}")
            return []
    
    async def increment_downloads(self, message_id: str, size: int = 0) -> bool:
        """Increment download counter and bandwidth"""
        try:
            await self.files.update_one(
                {"message_id": message_id},
                {
                    "$inc": {
                        "downloads": 1,
                        "bandwidth_used": size
                    }
                }
            )
            # Also update global bandwidth
            await self.update_bandwidth(size)
            return True
        except Exception as e:
            logger.error(f"Increment downloads error: {e}")
            return False
    
    # ==================== USER OPERATIONS ====================
    
    async def register_user(self, user_data: Dict) -> bool:
        """Register or update user"""
        try:
            user_doc = {
                "user_id": user_data["user_id"],
                "username": user_data.get("username", ""),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "first_used": datetime.utcnow(),
                "total_files": 0,
                "last_activity": datetime.utcnow()
            }
            
            await self.users.update_one(
                {"user_id": user_data["user_id"]},
                {
                    "$setOnInsert": {"first_used": user_doc["first_used"]},
                    "$set": {
                        "username": user_doc["username"],
                        "first_name": user_doc["first_name"],
                        "last_name": user_doc["last_name"],
                        "last_activity": user_doc["last_activity"]
                    },
                    "$inc": {"total_files": 1}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Register user error: {e}")
            return False
    
    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        try:
            return await self.users.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Get user error: {e}")
            return None
    
    # ==================== BANDWIDTH OPERATIONS ====================
    
    async def update_bandwidth(self, size: int) -> bool:
        """Update bandwidth usage"""
        try:
            today = datetime.utcnow().date().isoformat()
            await self.bandwidth.update_one(
                {"date": today},
                {
                    "$inc": {"total_bytes": size, "total_downloads": 1},
                    "$set": {"last_updated": datetime.utcnow()}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Update bandwidth error: {e}")
            return False
    
    async def get_total_bandwidth(self) -> int:
        """Get total bandwidth used"""
        try:
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$total_bytes"}}}
            ]
            result = await self.bandwidth.aggregate(pipeline).to_list(length=1)
            return result[0]["total"] if result else 0
        except Exception as e:
            logger.error(f"Get total bandwidth error: {e}")
            return 0
    
    async def get_bandwidth_stats(self) -> Dict:
        """Get bandwidth statistics"""
        try:
            total = await self.get_total_bandwidth()
            today = datetime.utcnow().date().isoformat()
            today_stats = await self.bandwidth.find_one({"date": today})
            
            return {
                "total_bandwidth": total,
                "today_bandwidth": today_stats.get("total_bytes", 0) if today_stats else 0,
                "today_downloads": today_stats.get("total_downloads", 0) if today_stats else 0
            }
        except Exception as e:
            logger.error(f"Get bandwidth stats error: {e}")
            return {"total_bandwidth": 0, "today_bandwidth": 0, "today_downloads": 0}
    
    # ==================== STATISTICS ====================
    
    async def get_stats(self) -> Dict:
        """Get bot statistics"""
        try:
            total_files = await self.files.count_documents({})
            total_users = await self.users.count_documents({})
            
            # Get total downloads
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$downloads"}}}
            ]
            downloads_result = await self.files.aggregate(pipeline).to_list(length=1)
            total_downloads = downloads_result[0]["total"] if downloads_result else 0
            
            # Get bandwidth stats
            bandwidth_stats = await self.get_bandwidth_stats()
            
            return {
                "total_files": total_files,
                "total_users": total_users,
                "total_downloads": total_downloads,
                "total_bandwidth": bandwidth_stats["total_bandwidth"],
                "today_bandwidth": bandwidth_stats["today_bandwidth"],
                "today_downloads": bandwidth_stats["today_downloads"]
            }
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {
                "total_files": 0,
                "total_users": 0,
                "total_downloads": 0,
                "total_bandwidth": 0,
                "today_bandwidth": 0,
                "today_downloads": 0
            }
    
    # ==================== SUDO USER OPERATIONS ====================
    
    async def add_sudo_user(self, user_id: str, added_by: str) -> bool:
        """Add sudo user"""
        try:
            sudo_doc = {
                "user_id": user_id,
                "added_by": added_by,
                "added_at": datetime.utcnow()
            }
            await self.sudo_users.update_one(
                {"user_id": user_id},
                {"$set": sudo_doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Add sudo user error: {e}")
            return False
    
    async def remove_sudo_user(self, user_id: str) -> bool:
        """Remove sudo user"""
        try:
            result = await self.sudo_users.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Remove sudo user error: {e}")
            return False
    
    async def is_sudo_user(self, user_id: str) -> bool:
        """Check if user is sudo"""
        try:
            result = await self.sudo_users.find_one({"user_id": user_id})
            return result is not None
        except Exception as e:
            logger.error(f"Is sudo user error: {e}")
            return False
    
    async def get_sudo_users(self) -> List[Dict]:
        """Get all sudo users"""
        try:
            cursor = self.sudo_users.find({})
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Get sudo users error: {e}")
            return []
    
    async def close(self):
        """Close database connection"""
        self.client.close()
