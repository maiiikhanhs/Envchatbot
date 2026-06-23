from app.database.mongo import get_collection, CONVERSATIONS_COLLECTION

def migrate():
    col = get_collection(CONVERSATIONS_COLLECTION)
    
    query = {"$or": [{"user_id": {"$exists": False}}, {"user_id": ""}, {"user_id": None}]}
    update = {"$set": {"user_id": "admin"}}
    
    result = col.update_many(query, update)
    print(f"Migrated {result.modified_count} conversations to 'admin'")

if __name__ == "__main__":
    migrate()
