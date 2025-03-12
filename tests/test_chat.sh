#!/usr/bin/env bash

CHAT_SERVICE_URL="http://localhost:8000"  # If chat-service is mapped to port 8000 on your host

# Send multiple messages
echo "Sending messages from Alice to Bob..."
curl -X POST -H "Content-Type: application/json" \
     -d '{"fromUser":"Alice","toUser":"Bob","content":"Hello Bob"}' \
     $CHAT_SERVICE_URL/send
echo

curl -X POST -H "Content-Type: application/json" \
     -d '{"fromUser":"Alice","toUser":"Bob","content":"Are you there?"}' \
     $CHAT_SERVICE_URL/send
echo

# Send messages from Bob to Alice
echo "Sending message from Bob to Alice..."
curl -X POST -H "Content-Type: application/json" \
     -d '{"fromUser":"Bob","toUser":"Alice","content":"Hey Alice, I am here!"}' \
     $CHAT_SERVICE_URL/send
echo

# Now let's see if the storage-service has stored them in Redis
cat <<EOF
Check Redis keys (requires redis-cli installed in your system or Docker exec):
docker exec -it redis redis-cli KEYS chat:*
docker exec -it redis redis-cli GET chat:Bob:<timestamp>
docker exec -it redis redis-cli GET chat:Alice:<timestamp>
EOF
