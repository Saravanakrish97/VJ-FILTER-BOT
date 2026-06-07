from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

class AnonDB:
    def __init__(self):
        self.client = AsyncIOMotorClient(DATABASE_URI)
        self.db = self.client[DATABASE_NAME]

        self.users = self.db["anon_users"]

    async def create_user(self, user_id):

        user = await self.users.find_one({"_id": user_id})

        if not user:

            await self.users.insert_one({
                "_id": user_id,
                "profile": {
                    "name": None,
                    "age": None,
                    "gender": None,
                    "location": None
                },
                "partner": None,
                "status": "idle"
            })

    async def set_profile(self, user_id, data):

        await self.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "profile": data
                }
            },
            upsert=True
        )

    async def get_user(self, user_id):

        user = await self.users.find_one({"_id": user_id})

        if not user:
            await self.create_user(user_id)
            user = await self.users.find_one({"_id": user_id})

        return user

    async def set_partner(self, user1, user2):

        await self.users.update_one(
            {"_id": user1},
            {
                "$set": {
                    "partner": user2,
                    "status": "chatting"
                }
            }
        )

        await self.users.update_one(
            {"_id": user2},
            {
                "$set": {
                    "partner": user1,
                    "status": "chatting"
                }
            }
        )

    async def clear_partner(self, user_id):

        await self.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "partner": None,
                    "status": "idle"
                }
            }
        )

    # ADD THIS
    async def reset_partners(self, user1, user2):

        await self.clear_partner(user1)
        await self.clear_partner(user2)

    # ADD THIS
    async def set_partners_atomic(self, user1, user2):

        await self.set_partner(user1, user2)


# IMPORTANT
anondb = AnonDB()
