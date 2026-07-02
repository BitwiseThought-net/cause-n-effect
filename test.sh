#!/usr/bin/env bash
set -e

SSL=false
HOST="localhost"
PORT=":8042"

# 1. Parse the command line argument for -host
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
      echo "Usage: ./test.sh -host <hostname>"
      exit 1
      ;;
  esac
done

# 2. Inject bash environment parameters cleanly into Python execution
CURL_COMMAND=$(env SSL="$SSL" HOST="$HOST" PORT="$PORT" .venv/bin/python3 -c '
import hmac, hashlib, json, os, sys

# Safely extract variables passed down from bash
target_ssl = os.getenv("SSL", "false").lower() == "true"
target_host = os.getenv("HOST", "localhost")
target_port = os.getenv("PORT", ":8042")

# Determine the correct URL schema based on the SSL boolean status
protocol = "https" if target_ssl else "http"

secret = ""
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.startswith("SECRET="):
                secret = line.strip().split("=", 1)[1].encode()

if not secret:
    print("ERROR: SECRET not found in .env file.")
    sys.exit(1)

body = b"{\"event\":\"user.created\",\"id\":\"usr_12345\"}"
sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

# Generates clean, adaptive execution string matching your environment profile
print(f"curl -s -L -X POST {protocol}://{target_host}{target_port}/ -H \"Content-Type: application/json\" -H \"X-Hub-Signature-256: {sig}\" -d '\''{{\"event\":\"user.created\",\"id\":\"usr_12345\"}}'\''")
')

if [[ "$CURL_COMMAND" == "ERROR:"* ]]; then
    echo "❌ $CURL_COMMAND Please run ./setup_env.sh first."
    exit 1
fi

echo ""
echo "--------------------------------------------------------"
echo "Generated Test Curl Command:"
echo "--------------------------------------------------------"
echo "$CURL_COMMAND" | sed 's/ -H/ \\\n  -H/g' | sed 's/ -d/ \\\n  -d/g'
echo "--------------------------------------------------------"
echo ""

# 3. Prompt the user for execution choice (Defaulting to Y)
read -p "Would you like to run this curl command now? [Y/n]: " USER_CHOICE
USER_CHOICE=$(echo "$USER_CHOICE" | tr '[:upper:]' '[:lower:]')
USER_CHOICE="${USER_CHOICE:-y}"

if [[ "$USER_CHOICE" == "y" || "$USER_CHOICE" == "yes" ]]; then
    echo "🚀 Executing request..."
    echo ""
    RESPONSE=$(eval "$CURL_COMMAND")
    echo "📥 Server Response: $RESPONSE"
    echo ""
else
    echo "⏭️ Skipped execution."
    echo ""
fi
