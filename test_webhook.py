import hmac
import hashlib
import json
import os
import sys
import requests

def send_signed_payload():
    # 1. Initialize default development endpoints
    ssl = False
    host = "localhost"
    port = ":8042"

    # 2. Parse command line arguments directly inside Python context
    args = sys.argv[1:]
    if "-host" in args:
        try:
            host_idx = args.index("-host")
            host = args[host_idx + 1]
            ssl = True
            port = ""  # Strip off port string for remote target mappings
        except IndexError:
            print("❌ Error: -host parameter requires an accompanying hostname argument.")
            return

    protocol = "https" if ssl else "http"

    # 3. Extract your authorization secret
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

    url = f"{protocol}://{host}{port}/"

    # 4. Craft your test tracking document package
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
    payload_bytes = json.dumps(payload).encode("utf-8")

    # 5. Generate secure signature
    signature = "sha256=" + hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature
    }

    print(f"🚀 Sending signed payload to {url}...")
    print(f"🔑 Generated Header Signature: {signature}")

    try:
        response = requests.post(url, data=payload_bytes, headers=headers)
        print(f"📡 Server Status Code: {response.status_code}")
        print(f"📥 Server Response Body: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ Connection Failed. Is your target environment reachable?")
    except Exception as e:
        print(f"⚠️ An unexpected error occurred: {e}")

if __name__ == "__main__":
    send_signed_payload()
