import os
import hmac
import hashlib
import json
import pika
from fastapi import FastAPI, Request, HTTPException, status
import uvicorn

app = FastAPI(title="Secure Webhook Queue Ingester")

# 1. Load configuration and secret keys from environment variables
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode("utf-8")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

# Safety check: Halt startup if core secrets are missing
if not WEBHOOK_SECRET:
    raise RuntimeError("CRITICAL: WEBHOOK_SECRET environment variable is not set!")
if not RABBITMQ_USER or not RABBITMQ_PASS:
    raise RuntimeError("CRITICAL: RabbitMQ credentials are not fully set in the environment!")

# 2. Establish authenticated connection to RabbitMQ broker
try:
    # Package credentials using the PlainCredentials handler
    credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    
    # Pass credentials into connection parameters
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Declare a durable queue that survives system restarts
    channel.queue_declare(queue='webhook_queue', durable=True)
    print("✅ Successfully authenticated and connected to RabbitMQ.")
except Exception as e:
    print(f"❌ Failed to connect to RabbitMQ: {e}")
    raise e

@app.post("/webhook")
async def receive_webhook(request: Request):
    # Enforce signature security check
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        
    body = await request.body()
    expected_signature = "sha256=" + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    # Push raw verified payload into the secure queue
    try:
        channel.basic_publish(
            exchange='',
            routing_key='webhook_queue',
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent  # Flushes message to disk
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to queue webhook payload: {e}"
        )
    
    return {"status": "queued", "message": "Webhook received and safely buffered."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)

