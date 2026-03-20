"""Tests for the signal event bus."""

import threading
import time

from services.autonomous_runner.signal_event_bus import (
    SignalEventBus,
    get_event_bus,
    reset_event_bus,
)


class TestSignalEventBus:
    def test_publish_delivers_to_subscribers(self):
        bus = SignalEventBus()
        received = []
        bus.subscribe("test-1", lambda e: received.append(e))
        bus.publish("signal", {"symbol": "BTC/USD"})
        assert len(received) == 1
        assert received[0]["data"]["symbol"] == "BTC/USD"
        assert received[0]["type"] == "signal"
        assert received[0]["id"] == 1

    def test_multiple_subscribers(self):
        bus = SignalEventBus()
        results_a = []
        results_b = []
        bus.subscribe("a", lambda e: results_a.append(e))
        bus.subscribe("b", lambda e: results_b.append(e))
        delivered = bus.publish("signal", {"action": "BUY"})
        assert delivered == 2
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_unsubscribe(self):
        bus = SignalEventBus()
        received = []
        bus.subscribe("test-1", lambda e: received.append(e))
        bus.unsubscribe("test-1")
        bus.publish("signal", {"symbol": "ETH/USD"})
        assert len(received) == 0

    def test_replay_buffer(self):
        bus = SignalEventBus(replay_buffer_size=5)
        for i in range(10):
            bus.publish("signal", {"idx": i})
        # Buffer should only keep last 5
        replay = bus.get_replay_buffer(since_id=0)
        assert len(replay) == 5
        assert replay[0]["data"]["idx"] == 5

    def test_replay_buffer_since_id(self):
        bus = SignalEventBus()
        bus.publish("signal", {"a": 1})
        bus.publish("signal", {"b": 2})
        bus.publish("signal", {"c": 3})
        replay = bus.get_replay_buffer(since_id=2)
        assert len(replay) == 1
        assert replay[0]["data"]["c"] == 3

    def test_failed_subscriber_doesnt_block_others(self):
        bus = SignalEventBus()
        received = []

        def bad_callback(e):
            raise RuntimeError("subscriber error")

        bus.subscribe("bad", bad_callback)
        bus.subscribe("good", lambda e: received.append(e))
        delivered = bus.publish("signal", {"ok": True})
        assert delivered == 1  # Only good subscriber
        assert len(received) == 1

    def test_stats(self):
        bus = SignalEventBus(replay_buffer_size=50)
        bus.subscribe("s1", lambda e: None)
        bus.publish("signal", {"x": 1})
        bus.publish("signal", {"x": 2})
        stats = bus.get_stats()
        assert stats["total_events"] == 2
        assert stats["subscriber_count"] == 1
        assert stats["replay_buffer_size"] == 2
        assert stats["replay_buffer_capacity"] == 50

    def test_thread_safety(self):
        bus = SignalEventBus()
        results = []
        bus.subscribe("t", lambda e: results.append(e))

        def publisher():
            for i in range(50):
                bus.publish("signal", {"i": i})

        threads = [threading.Thread(target=publisher) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 200

    def test_global_singleton(self):
        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
        reset_event_bus()

    def test_event_has_timestamp(self):
        bus = SignalEventBus()
        received = []
        bus.subscribe("ts", lambda e: received.append(e))
        bus.publish("signal", {})
        assert "timestamp" in received[0]
        assert isinstance(received[0]["timestamp"], float)
