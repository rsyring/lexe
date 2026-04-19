from datetime import datetime
from os import environ

from flask import Flask
import redis


if environ.get('FLASK_DEBUG'):
    # Local development
    # $ docker compose up -d redis
    REDIS_HOST = 'localhost'

elif environ.get('JUKE_STACK'):
    # Juke deployment
    REDIS_HOST = 'redis.juke'

else:
    # Presumably Docker compose to check the built image without needing to push/pull to a registry
    # $ docker compose up -d redis
    # $ docker compose up --build web
    REDIS_HOST = 'redis'


app = Flask(__name__)
redis_client = redis.Redis(host=REDIS_HOST, decode_responses=True)


@app.route('/')
def hello():
    # Increment visit counter
    count = redis_client.incr('visit_count')
    return f"""
        <p>Hello, World!</p>
        <p>Visit count: {count}</p>
        <p><small>{datetime.now()}</small></p>
    """
