import os
import sys
import time
import json
import pika

def process_webhook_payload(ch, method, properties, body):
    print(f"📥 [Worker] Received message from queue.")
    
    try:
        # Decode and parse the raw JSON data
        payload = json.loads(body.decode('utf-8'))
        print(f"⚙️ [Worker] Processing payload data: {payload}")
        
        # --- PLACE YOUR HEAVY BUSINESS LOGIC HERE ---
        # e.g., Update database, send emails, trigger APIs, etc.
        time.sleep(2) # Simulating a heavy 2-second processing task
        # ---------------------------------------------
        
        print("✅ [Worker] Task completed successfully.")
        
        # Acknowledge the message was processed safely
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError:
        print("❌ [Worker] Failed to parse JSON body. Rejecting message.")
        # Reject malformed data entirely (don't requeue it to avoid infinite loops)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=false)
    except Exception as e:
        print(f"⚠️ [Worker] Error processing message: {e}. Requeuing...")
        # Put the message back on the queue to retry later
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    # Load environment configuration
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_USER = os.getenv("RABBITMQ_USER")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

    if not RABBITMQ_USER or not RABBITMQ_PASS:
        print("CRITICAL: RabbitMQ credentials are not set in the worker environment!")
        sys.exit(1)

    print("🚀 [Worker] Starting background consumer...")
    
    try:
        credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Ensure the queue exists and is durable
        channel.queue_declare(queue='webhook_queue', durable=True)
        
        # Fair dispatch: tells RabbitMQ not to give more than 1 message to a worker at a time
        channel.basic_qos(prefetch_count=1)
        
        # Attach the callback function to the queue
        channel.basic_consume(queue='webhook_queue', on_message_callback=process_webhook_payload)
        
        print("🛸 [Worker] Waiting for messages. To exit press CTRL+C")
        channel.start_consuming()
        
    except Exception as e:
        print(f"❌ [Worker] Connection lost or failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
