import hmac
import hashlib
import json
import os
import requests

def send_signed_payload():
    # 1. Parse and extract variables directly from your local .env file
    secret_key = None
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("SECRET="):
                    secret_key = line.strip().split("=", 1)[1].encode("utf-8")
                    break

    if not secret_key:
        print("❌ Error: Could not find SECRET inside your .env file.")
        print("Please run your setup_env.sh script first.")
        return

    # 2. Define the endpoint URL (Mapping to the external port we locked down)
    url = "http://localhost:8042/"
    
    # 3. Create a realistic JSON test payload
    payload = {
        "event": "order.completed",
        "timestamp": 1719600000,
        "data": {
            "order_id": "ORD-987654",
            "amount": 149.99,
            "currency": "USD",
            "customer_email": "test-user@example.com"
        }
    }
    
    # Convert payload dictionary cleanly to bytes
    payload_bytes = json.dumps(payload).encode("utf-8")
    
    # 4. Generate the exact SHA256 HMAC cryptographic signature
    signature = "sha256=" + hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()
    
    # 5. Pack the required signature header
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature
    }
    
    print(f"🚀 Sending signed payload to {url}...")
    print(f"🔑 Generated Header Signature: {signature}")
    
    try:
        # Send the POST request
        response = requests.post(url, data=payload_bytes, headers=headers)
        
        print(f"📡 Server Status Code: {response.status_code}")
        print(f"📥 Server Response Body: {response.json()}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Failed. Is your Docker Compose environment running?")
        print("Run: docker compose up -d")
    except Exception as e:
        print(f"⚠️ An error occurred: {e}")

if __name__ == "__main__":
    send_signed_payload()
