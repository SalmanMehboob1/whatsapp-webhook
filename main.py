import os
import asyncpg
from datetime import datetime
from fastapi import FastAPI, Request, Query
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Webhook", version="1.0")

DATABASE_URL = os.getenv("DATABASE_URL")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# Global database connection pool
pool = None

# ==================== STARTUP & SHUTDOWN ====================

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    print(" Database connection pool created.")
@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()
        print(" Database connection pool closed.")

# ==================== DATABASE HELPER ====================

async def save_message(phone_number: str, content: str, message_time: datetime, message_id: str):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO messages (phone_number, content, message_time, message_id) 
               VALUES ($1, $2, $3, $4)""",
            phone_number, content, message_time, message_id
        )
        print(f" Saved message from {phone_number}: {content[:50]}...")

# ==================== ROUTES ====================

@app.get("/")
async def health_check():
    return {"status": "WhatsApp Webhook is running!", "docs": "/docs"}

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: int = Query(..., alias="hub.challenge")
):
    """
    Meta sends a GET request to verify your webhook URL.
    """
    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return hub_challenge
    return {"error": "Verification failed"}, 403

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Meta sends a POST request with incoming messages.
    """
    data = await request.json()
    
    if data.get("entry"):
        for entry in data["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    phone_number = message.get("from")
                    content = message.get("text", {}).get("body", "")
                    timestamp = message.get("timestamp")
                    message_id = message.get("id")
                    
                    # Convert Unix timestamp to datetime
                    if timestamp:
                        message_time = datetime.fromtimestamp(int(timestamp))
                    else:
                        message_time = datetime.now()
                    
                    # Save to database asynchronously
                    await save_message(phone_number, content, message_time, message_id)
    
    return {"status": "OK"}
