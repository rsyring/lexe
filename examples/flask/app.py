from datetime import datetime
from os import environ

from flask import Flask
import redis


if environ.get('FLASK_DEBUG'):
    # Local development
    # $ docker compose up -d redis
    REDIS_HOST = 'localhost'

else:
    # Docker Compose, including lexe deploys
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
