"""Fan one room's events out to everyone watching it.

A room is the first thing in this app where something happens that the client didn't
ask for: someone else types, the clock runs out, the bot takes its turn. Those have to
reach every browser in the room, and none of them are replies to a request.

In-process, deliberately. The backend is deployed with `--max-instances 1`, so every
connection to a room lands in the same Python process and a dictionary of queues is
the whole of the infrastructure - no Redis, no pub/sub topic, no second thing to
deploy and keep alive. If that ever stops being true this file is the seam: swap the
dict for a real broker and nothing above it changes.

Each subscriber gets its own unbounded queue rather than sharing a cursor, so a slow
reader delays only itself. A subscriber that goes away without unsubscribing leaks one
queue until the room is dropped, which is a few hundred bytes and bounded by how many
tabs a room ever had open.
"""

import queue
import threading


class Bus:
    def __init__(self):
        self._topics = {}                       # topic -> {queue}
        self._lock = threading.Lock()

    def subscribe(self, topic):
        q = queue.Queue()
        with self._lock:
            self._topics.setdefault(topic, set()).add(q)
        return q

    def unsubscribe(self, topic, q):
        with self._lock:
            listeners = self._topics.get(topic)
            if listeners:
                listeners.discard(q)
                if not listeners:
                    del self._topics[topic]

    def publish(self, topic, kind, data):
        """Hand `(kind, data)` to everyone on this topic.

        The set is copied under the lock and written to outside it: publishing happens
        on a turn's worker thread, and holding the lock across the puts would make one
        room's fan-out block every other room's subscribe.
        """
        with self._lock:
            listeners = list(self._topics.get(topic, ()))
        for q in listeners:
            q.put((kind, data))

    def listeners(self, topic):
        with self._lock:
            return len(self._topics.get(topic, ()))


BUS = Bus()
