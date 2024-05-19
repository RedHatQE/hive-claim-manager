#!/bin/bash

set -ep
redis-server redis.conf &
while ! redis-cli ping; do sleep 1; done
echo "Redis started"

poetry run python api/api.py &
while ! curl http://127.0.0.1:5000; do sleep 1; done
echo "API started"

npm run start-server
