import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["envchat_db"]
msgs = list(db["messages"].find({}).sort("created_at", -1).limit(5))
for m in msgs:
    print(m)
