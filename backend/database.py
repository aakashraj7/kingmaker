import os
import json
import uuid
from datetime import datetime
from pymongo import MongoClient
import pymongo.errors

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# List of collections needed for Kingmaker
COLLECTIONS = [
    "users",
    "conversations",
    "messages",
    "files",
    "profiles",
    "achievements",
    "roadmaps",
    "notifications"
]

class JSONCollection:
    """Fallback file-based collection mimicking MongoDB collection interface."""
    def __init__(self, name):
        self.name = name
        self.filepath = os.path.join(DATA_DIR, f"{name}.json")
        if not os.path.exists(self.filepath):
            self._save([])

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except Exception:
            return []

    def _save(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def find(self, query=None):
        query = query or {}
        records = self._load()
        results = []
        for r in records:
            match = True
            for k, v in query.items():
                if k == "id" and "id" not in r and "_id" in r:
                    if str(r["_id"]) != str(v):
                        match = False
                        break
                elif r.get(k) != v:
                    match = False
                    break
            if match:
                # Add string 'id' for compatibility
                if "_id" in r and "id" not in r:
                    r["id"] = r["_id"]
                results.append(r)
        return results

    def find_one(self, query=None):
        res = self.find(query)
        return res[0] if res else None

    def insert_one(self, doc):
        records = self._load()
        doc = dict(doc)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        doc["id"] = doc["_id"]
        
        now = datetime.utcnow().isoformat()
        doc["createdAt"] = now
        doc["updatedAt"] = now
        
        records.append(doc)
        self._save(records)
        return doc

    def update_one(self, query, update_dict):
        records = self._load()
        doc = self.find_one(query)
        if not doc:
            return None
            
        # Extract $set key if present
        patch = update_dict.get("$set", update_dict)
        
        idx = -1
        for i, r in enumerate(records):
            if r.get("_id") == doc.get("_id"):
                idx = i
                break
                
        if idx != -1:
            records[idx].update(patch)
            records[idx]["updatedAt"] = datetime.utcnow().isoformat()
            self._save(records)
            if "id" not in records[idx]:
                records[idx]["id"] = records[idx]["_id"]
            return records[idx]
        return None

    def delete_one(self, query):
        records = self._load()
        doc = self.find_one(query)
        if not doc:
            return False
            
        next_records = [r for r in records if r.get("_id") != doc.get("_id")]
        self._save(next_records)
        return len(records) > len(next_records)

    def delete_many(self, query):
        records = self._load()
        original_len = len(records)
        next_records = []
        for r in records:
            match = True
            for k, v in query.items():
                if r.get(k) != v:
                    match = False
                    break
            if not match:
                next_records.append(r)
        self._save(next_records)
        return original_len - len(next_records)


class RealMongoCollection:
    """Wrapper around real pymongo collection to standardize ID mapping."""
    def __init__(self, collection):
        self.coll = collection

    def find(self, query=None):
        query = query or {}
        # Convert 'id' in query to '_id' for mongo compatibility
        if "id" in query:
            query["_id"] = query.pop("id")
        results = list(self.coll.find(query))
        for r in results:
            r["id"] = str(r["_id"])
        return results

    def find_one(self, query=None):
        query = query or {}
        if "id" in query:
            query["_id"] = query.pop("id")
        r = self.coll.find_one(query)
        if r:
            r["id"] = str(r["_id"])
        return r

    def insert_one(self, doc):
        doc = dict(doc)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        doc["createdAt"] = now
        doc["updatedAt"] = now
        
        self.coll.insert_one(doc)
        doc["id"] = str(doc["_id"])
        return doc

    def update_one(self, query, update_dict):
        if "id" in query:
            query["_id"] = query.pop("id")
            
        # Ensure $set wraps the update if it doesn't already
        if not any(k.startswith("$") for k in update_dict.keys()):
            update_dict = {"$set": update_dict}
            
        # Add updatedAt timestamp
        if "$set" in update_dict:
            update_dict["$set"]["updatedAt"] = datetime.utcnow().isoformat()
            
        self.coll.update_one(query, update_dict)
        return self.find_one(query)

    def delete_one(self, query):
        if "id" in query:
            query["_id"] = query.pop("id")
        res = self.coll.delete_one(query)
        return res.deleted_count > 0

    def delete_many(self, query):
        res = self.coll.delete_many(query)
        return res.deleted_count


class DatabaseManager:
    """Database selector that handles real MongoDB connection or falls back to JSON files."""
    def __init__(self):
        self.client = None
        self.mongo_db = None
        self.use_real_mongo = False
        self.collections = {}
        
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "kingmaker")
        
        print(f"[Database] Attempting connection to MongoDB at: {mongo_uri}")
        try:
            # Short timeout so it doesn't block startup if local Mongo isn't running
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            # Force call to verify connection status
            self.client.server_info()
            self.mongo_db = self.client[db_name]
            self.use_real_mongo = True
            print(f"[Database] Success! Connected to real MongoDB database: '{db_name}'")
        except pymongo.errors.PyMongoError as e:
            print("[Database] ⚠️ Local MongoDB not detected or running.")
            print(f"[Database] Message: {e}")
            print(f"[Database] Falling back to file-based JSON database under: {DATA_DIR}")
            self.use_real_mongo = False

        # Initialize collections
        for name in COLLECTIONS:
            if self.use_real_mongo:
                self.collections[name] = RealMongoCollection(self.mongo_db[name])
            else:
                self.collections[name] = JSONCollection(name)

    def __getattr__(self, name):
        if name in self.collections:
            return self.collections[name]
        raise AttributeError(f"DatabaseManager has no collection '{name}'")


# Singleton instance of database manager
db = DatabaseManager()
