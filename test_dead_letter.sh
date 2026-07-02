#!/usr/bin/env bash
set -e

SSL=false
HOST="localhost"
PORT=":8042"

while [[ $# -gt 0 ]]; do
  case $1 in
    -host)
      SSL=true
      HOST="$2"
      PORT=""
      shift 2
      ;;
    *)
      echo "❌ Unknown parameter: $1"
      echo "Usage: ./DeadLetterTest.sh [-host <hostname>]"
      exit 1
      ;;
  esac
done

# Pass bash configurations down to Python context
env SSL="$SSL" HOST="$HOST" PORT="$PORT" .venv/bin/python3 -c '
import hmac, hashlib, json, os, sys, requests

target_ssl = os.getenv("SSL", "false").lower() == "true"
target_host = os.getenv("HOST", "localhost")
target_port = os.getenv("PORT", ":8042")
protocol = "https" if target_ssl else "http"

secret = b""
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.startswith("SECRET="):
                secret = line.strip().split("=", 1)[1].encode()

if not secret:
    print("❌ Error: SECRET missing from .env file.")
    sys.exit(1)

# Poison payload targeting your workers trigger_error hook
body = b"{\"event\":\"order.failed_test\",\"data\":{\"id\":\"usr_123\",\"trigger_error\":true}}"
sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

headers = {"Content-Type": "application/json", "X-Hub-Signature-256": sig}
url = f"{protocol}://{target_host}{target_port}/"

print(f"🚀 Sending signed failure-trigger payload to {url}...")
try:
    # requests natively follows redirects (equivalent to curl -L)
    response = requests.post(url, data=body, headers=headers)
    print(f"📥 Server Response: {response.json()}")
except Exception as e:
    print(f"❌ Network transaction failed: {e}")
'
