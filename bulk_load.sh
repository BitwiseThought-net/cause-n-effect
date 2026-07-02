#!/usr/bin/env bash
set -e

# Default settings
NUM_ITEMS=10
SSL=false
HOST="localhost"
PORT=":8042"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -num)
      NUM_ITEMS="$2"
      shift 2
      ;;
    -host)
      SSL=true
      HOST="$2"
      PORT=""
      shift 2
      ;;
    *)
      echo "❌ Unknown parameter: $1"
      echo "Usage: ./bulk_load.sh -num <items> [-host <hostname>]"
      exit 1
      ;;
  esac
done

# Validate item count integer
if ! [[ "$NUM_ITEMS" =~ ^[0-9]+$ ]] || [ "$NUM_ITEMS" -le 0 ]; then
  echo "❌ Error: -num must be a positive integer."
  exit 1
fi

# 1. Generate the absolute, finalized curl statement directly out of Python to protect spacing
BASE_CURL_COMMAND=$(env SSL="$SSL" HOST="$HOST" PORT="$PORT" .venv/bin/python3 -c '
import hmac, hashlib, json, os, sys

target_ssl = os.getenv("SSL", "false").lower() == "true"
target_host = os.getenv("HOST", "localhost")
target_port = os.getenv("PORT", ":8042")
protocol = "https" if target_ssl else "http"

secret = ""
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.startswith("SECRET="):
                secret = line.strip().split("=", 1)[1].encode()

if not secret:
    print("ERROR")
    sys.exit(1)

body = b"{\"event\":\"bulk.load_test\",\"data\":{\"id\":\"bulk_item\",\"type\":\"benchmark\"}}"
sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
url = f"{protocol}://{target_host}{target_port}/"

# Build a clean base curl command string
print(f"curl -s -L -X POST {url} -H \"Content-Type: application/json\" -H \"X-Hub-Signature-256: {sig}\" -d '\''{body.decode()}'\''")
')

if [ "$BASE_CURL_COMMAND" = "ERROR" ]; then
    echo "❌ Error: SECRET not found in .env file. Run ./setup_env.sh first."
    exit 1
fi

echo "🚀 Bombarding endpoint with $NUM_ITEMS items..."
echo "--------------------------------------------------------"

START_TIME=$(date +%s)

# 2. Fire the loop using eval on the pre-built command
for ((i=1; i<=NUM_ITEMS; i++)); do
  # Redirect any residual standard output out of the terminal loop
  eval "$BASE_CURL_COMMAND" > /dev/null
    
  if (( i % 50 == 0 )) || (( i == NUM_ITEMS )); then
     echo "✅ Sent $i / $NUM_ITEMS items..."
  fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "--------------------------------------------------------"
echo "🏁 Done! Successfully injected $NUM_ITEMS items into the pipeline in ${DURATION}s."
