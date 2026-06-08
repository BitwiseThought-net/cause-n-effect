#!/usr/bin/env bash

set -e

ENV_FILE=".env"

# 1. Generate fresh cryptographic values using openssl
GEN_WEBHOOK_SECRET=$(openssl rand -hex 32)
GEN_RABBIT_PASS=$(openssl rand -hex 12)

# Case A: File does not exist -> Create it with all fresh values
if [ ! -f "$ENV_FILE" ]; then
    cat << EOF > "$ENV_FILE"
WEBHOOK_SECRET=$GEN_WEBHOOK_SECRET
RABBITMQ_USER=admin
RABBITMQ_PASS=$GEN_RABBIT_PASS
EOF
    echo "✨ Created a fresh '$ENV_FILE' file with all secret variables populated!"

# Case B: File exists -> Update WEBHOOK_SECRET and add RabbitMQ fields if missing
else
    # Helper variable to check if we need to add a trailing newline before appending
    NEED_NEWLINE=false
    if [ -s "$ENV_FILE" ] && [ "$(tail -c 1 "$ENV_FILE")" != "" ]; then
        NEED_NEWLINE=true
    fi

    # Update or append WEBHOOK_SECRET
    if grep -q "^WEBHOOK_SECRET=" "$ENV_FILE"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/^WEBHOOK_SECRET=.*/WEBHOOK_SECRET=$GEN_WEBHOOK_SECRET/" "$ENV_FILE"
        else
            sed -i "s/^WEBHOOK_SECRET=.*/WEBHOOK_SECRET=$GEN_WEBHOOK_SECRET/" "$ENV_FILE"
        fi
        echo "🔄 Updated 'WEBHOOK_SECRET' inside your existing '$ENV_FILE' file!"
    else
        [ "$NEED_NEWLINE" = true ] && echo "" >> "$ENV_FILE" && NEED_NEWLINE=false
        echo "WEBHOOK_SECRET=$GEN_WEBHOOK_SECRET" >> "$ENV_FILE"
        echo "➕ Appended missing 'WEBHOOK_SECRET' to your '$ENV_FILE' file!"
    fi

    # Append RABBITMQ_USER if completely missing
    if ! grep -q "^RABBITMQ_USER=" "$ENV_FILE"; then
        [ "$NEED_NEWLINE" = true ] && echo "" >> "$ENV_FILE" && NEED_NEWLINE=false
        echo "RABBITMQ_USER=admin" >> "$ENV_FILE"
        echo "➕ Appended missing 'RABBITMQ_USER' to your '$ENV_FILE' file!"
    fi

    # Append RABBITMQ_PASS if completely missing
    if ! grep -q "^RABBITMQ_PASS=" "$ENV_FILE"; then
        [ "$NEED_NEWLINE" = true ] && echo "" >> "$ENV_FILE" && NEED_NEWLINE=false
        echo "RABBITMQ_PASS=$GEN_RABBIT_PASS" >> "$ENV_FILE"
        echo "➕ Appended missing 'RABBITMQ_PASS' to your '$ENV_FILE' file!"
    fi
fi
