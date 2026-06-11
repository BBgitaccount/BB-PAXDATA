import json
import os
import queue
import sys
import threading

import redis

# project path setup
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)
from bb_paxdata.config.settings import get_settings

# Thread-safe queue to store events received from Redis Pub/Sub
event_queue = queue.Queue()
_listener_thread = None
_lock = threading.Lock()


def start_listener():
    """Start the background Redis Pub/Sub listener thread."""
    global _listener_thread
    with _lock:
        if _listener_thread is not None and _listener_thread.is_alive():
            return

        _listener_thread = threading.Thread(
            target=_redis_listener, name="RedisPubSubListener", daemon=True
        )
        _listener_thread.start()


def _redis_listener():
    """Target function for the background thread that listens to Redis."""
    try:
        settings = get_settings()
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        pubsub.subscribe("verdict_events")

        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    event_queue.put(payload)
                except Exception:
                    pass
    except Exception:
        # Fail silently in case Redis connection is not available
        pass


def get_new_events() -> list:
    """Retrieve all pending events from the thread-safe queue."""
    events = []
    while not event_queue.empty():
        try:
            events.append(event_queue.get_nowait())
        except queue.Empty:
            break
    return events
