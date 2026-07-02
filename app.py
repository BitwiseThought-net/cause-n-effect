import os
import hmac
import hashlib
import json
import pika
from fastapi import FastAPI, Request, HTTPException, status
import uvicorn

app = FastAPI(title="Secure Webhook Queue Ingester")

# Load configuration and secret keys from environment variables
SECRET_STR = os.getenv("SECRET", "")
SECRET = SECRET_STR.encode("utf-8")
API_KEY = os.getenv("API_KEY", "")  # Long-lived token for simple/mobile integrations
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

# Strict Startup Configuration Validation
if not SECRET_STR:
    raise RuntimeError("CRITICAL STARTUP ERROR: The 'SECRET' environment variable is missing or empty!")

if not API_KEY:
    raise RuntimeError("CRITICAL STARTUP ERROR: The 'API_KEY' environment variable is missing or empty!")

if not RABBITMQ_USER:
    raise RuntimeError("CRITICAL STARTUP ERROR: The 'RABBITMQ_USER' environment variable is missing or empty!")

if not RABBITMQ_PASS:
    raise RuntimeError("CRITICAL STARTUP ERROR: The 'RABBITMQ_PASS' environment variable is missing or empty!")


@app.post("/")
async def receive(request: Request):
    # Capture the raw request body payload bytes upfront
    body = await request.body()
    
    # 1. Dual Authorization Layer: Evaluate if a Tasker Bearer Token is present
    auth_header = request.headers.get("Authorization")
    if auth_header == f"Bearer {API_KEY}":
        # Request originates from your authenticated mobile device. 
        # Safety is handled by HTTPS transit encryption. Skip dynamic hash verification.
        pass
    else:
        # 2. Fallback: Require the strict dynamic HMAC cryptographic signature check for automated scripts
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Missing authorization headers"
            )
            
        expected_signature = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Invalid authorization signature"
            )

    # 3. Securely pass the validated payload to the RabbitMQ Broker Infrastructure
    try:
        credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Setup Dead Letter Exchange topology components
        channel.exchange_declare(exchange='dlx_exchange', exchange_type='topic')
        
        # Main Active Consumer Queue
        channel.queue_declare(
            queue='queue', 
            durable=True,
            arguments={
                'x-dead-letter-exchange': 'dlx_exchange',
                'x-dead-letter-routing-key': 'retry'
            }
        )
        
        # Asynchronous 5-second Backoff Timer/Retry Queue
        channel.queue_declare(
            queue='retry_queue', 
            durable=True,
            arguments={
                'x-dead-letter-exchange': '',
                'x-dead-letter-routing-key': 'queue',
                'x-message-ttl': 5000
            }
        )
        channel.queue_bind(exchange='dlx_exchange', queue='retry_queue', routing_key='retry')
        
        # Permanent Error Isolation Storage (Dead Letter Queue)
        channel.queue_declare(queue='dead_letter_queue', durable=True)
        channel.queue_bind(exchange='dlx_exchange', queue='dead_letter_queue', routing_key='dead')
        
        # Drop the payload message securely onto the active line
        channel.basic_publish(
            exchange='',
            routing_key='queue',
            body=body,
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
        )
        connection.close()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Message Broker Transaction Failure: {str(e)}"
        )
    
    return {"status": "queued", "message": "Received and safely buffered."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
