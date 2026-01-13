#!/bin/bash
  BASE_URL="http://localhost:8000"
  TOKEN="YOUR_ACCESS_TOKEN"

  echo "=== Health ==="
  curl -s $BASE_URL/health | jq

  echo -e "\n=== Tools List ==="
  curl -s -X POST $BASE_URL/mcp/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq '.result.tools[].name'

  echo -e "\n=== List Chats ==="
  curl -s -X POST $BASE_URL/mcp/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_chats","arguments":{"limit":3}}}' | jq