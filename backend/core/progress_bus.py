from collections import defaultdict
from queue import Queue

_streams: dict[str, Queue] = defaultdict(Queue)


def push(event_id: str, data: dict):
    _streams[event_id].put(data)


def stream(event_id: str):
    q = _streams[event_id]
    try:
        while True:
            data = q.get()
            yield f"data: {data}\n\n"
            if data.get("done"):
                break
    finally:
        _streams.pop(event_id, None)
