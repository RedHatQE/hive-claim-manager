#!/bin/bash

set -ep
redis-server redis.conf &
while ! redis-cli ping; do sleep 1; done
echo "Redis started"

pushd api/
poetry run python manage_users.py create_db

if [[ -z $DEVELOPMENT ]]; then
	poetry run uwsgi --post-buffering --master --enable-threads --http 0.0.0.0:5000 --wsgi-file api.py --callable app --processes 4 --threads 2 &
else
	poetry run python api.py &
fi

while ! curl http://127.0.0.1:5000/api/healtcheck; do sleep 1; done
echo "API started"
popd

if [[ -z $DEVELOPMENT ]]; then
	serve -s build
else
	./node_modules/.bin/env-cmd -f .env npm run start-server
fi
