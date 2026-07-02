import os
import sys
import json
import time
import pika
from pymongo import MongoClient

# Global MongoDB Client configuration placeholders
db = None
payload_collection = None

def get_retry_count(properties):
    if properties.headers and 'x-death' in properties.headers:
        death_log = properties.headers['x-death']
        if isinstance(death_log, list) and len(death_log) > 0:
            return sum(hop.get('count', 0) for hop in death_log)
    return 0

def process_payload(ch, method, properties, body):
    print("📥 [Worker] Processing an incoming message.")
    retry_count = get_retry_count(properties)
    MAX_RETRIES = 3
    
    try:
        # 1. Parse payload out of RabbitMQ string format
        payload = json.loads(body.decode('utf-8'))
        
        # Simulated failure hook for testing
        if payload.get("data", {}).get("trigger_error") is True:
            raise RuntimeError("Simulated internal system dependency crash.")
            
        # 2. Append processing metadata and insert into MongoDB
        payload["_processed_at"] = time.time()
        payload["_retry_count"] = retry_count
        
        # Save straight to the database
        insert_result = payload_collection.insert_one(payload)
        print(f"💾 [Worker] Safely stored payload in MongoDB with ID: {insert_result.inserted_id}")
        
        # 3. Acknowledge the message was successfully cleared
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        print(f"⚠️ [Worker] Error processing message: {e}")
        
        if retry_count >= MAX_RETRIES:
            print(f"🚨 [Worker] Message exceeded {MAX_RETRIES} attempts. Sending to permanent Dead Letter Queue.")
            ch.basic_publish(
                exchange='dlx_exchange',
                routing_key='dead',
                body=body,
                properties=properties
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            print(f"🔄 [Worker] Attempt {retry_count + 1} failed. Moving to 5s retry backoff stream...")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    global db, payload_collection
    
    # Load environment variables
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_USER = os.getenv("RABBITMQ_USER")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = os.getenv("MONGO_PORT", "27017")

    if not RABBITMQ_USER or not RABBITMQ_PASS:
        print("CRITICAL: RabbitMQ credentials are not set in the worker environment!")
        sys.exit(1)

    # Connect to MongoDB Database Engine
    try:
        print(f"🔌 Connecting to MongoDB at {MONGO_HOST}:{MONGO_PORT}...")
        mongo_client = MongoClient(host=MONGO_HOST, port=int(MONGO_PORT))
        # Access database 'causality' and collection 'payloads'
        db = mongo_client["causality"]
        payload_collection = db["payloads"]
        print("✅ MongoDB Connection Established Successfully.")
    except Exception as mongo_err:
        print(f"❌ Failed to connect to MongoDB: {mongo_err}")
        sys.exit(1)

    # Connect to RabbitMQ Broker Engine
    credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # RabbitMQ Topology Layout Definitions
    channel.exchange_declare(exchange='dlx_exchange', exchange_type='topic')
    channel.queue_declare(
        queue='queue', 
        durable=True,
        arguments={
            'x-dead-letter-exchange': 'dlx_exchange',
            'x-dead-letter-routing-key': 'retry'
        }
    )
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
    channel.queue_declare(queue='dead_letter_queue', durable=True)
    channel.queue_bind(exchange='dlx_exchange', queue='dead_letter_queue', routing_key='dead')

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='queue', on_message_callback=process_payload)
    
    print("🛸 [Worker] Listening for tasks...")
    channel.start_consuming()

if __name__ == '__main__':
    main()
