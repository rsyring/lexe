from datetime import datetime
from html import escape
from os import environ
from pathlib import Path

from flask import Flask
import redis


REDIS_HOST = 'localhost' if environ.get('FLASK_DEBUG') else 'redis'


app = Flask(__name__)
redis_client = redis.Redis(host=REDIS_HOST, decode_responses=True)
DATA_DPATH = Path('/home/pyapp/data')
EVENTS_LOG_FPATH = DATA_DPATH / 'events.log'
STARTUP_SENTINEL_FPATH = Path('/tmp/flask-app-started')


def append_event(name: str) -> None:
    DATA_DPATH.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOG_FPATH.open('a', encoding='utf-8') as events_file:
        events_file.write(f'{datetime.now().isoformat()} {name}\n')


def record_startup_event() -> None:
    try:
        STARTUP_SENTINEL_FPATH.touch(exist_ok=False)
    except FileExistsError:
        return
    append_event('app.py startup')


def events_tail(limit: int = 15) -> str:
    if not EVENTS_LOG_FPATH.exists():
        return 'missing'
    lines = EVENTS_LOG_FPATH.read_text(encoding='utf-8').splitlines()
    return '\n'.join(lines[-limit:])


record_startup_event()


@app.route('/')
def hello():
    # Increment visit counter
    count = redis_client.incr('visit_count')
    events_text = escape(events_tail())
    return f"""
        <p>Hello, World!</p>
        <p>Visit count: {count}</p>
        <p><small>{datetime.now()}</small></p>
        <pre>{events_text}</pre>
    """
