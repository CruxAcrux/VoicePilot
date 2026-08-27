"""Unit tests for the EventBus."""

from voicepilot.core.events import Event, EventBus, EventType


def test_subscribe_and_publish():
    bus = EventBus()
    received = []

    @bus.subscribe(EventType.TRANSCRIPTION_READY)
    def handler(event: Event) -> None:
        received.append(event)

    bus.publish(Event(type=EventType.TRANSCRIPTION_READY, data={"text": "hello"}))
    assert len(received) == 1
    assert received[0].data["text"] == "hello"


def test_multiple_subscribers():
    bus = EventBus()
    log = []

    bus.on(EventType.ACTION_COMPLETED, lambda e: log.append("a"))
    bus.on(EventType.ACTION_COMPLETED, lambda e: log.append("b"))

    bus.publish_type(EventType.ACTION_COMPLETED)
    assert log == ["a", "b"]


def test_unsubscribe():
    bus = EventBus()
    called = []

    def handler(e):
        called.append(True)

    bus.on(EventType.APP_READY, handler)
    bus.off(EventType.APP_READY, handler)
    bus.publish_type(EventType.APP_READY)

    assert called == []


def test_exception_in_subscriber_does_not_block_others():
    bus = EventBus()
    log = []

    def bad_handler(e):
        raise RuntimeError("boom")

    def good_handler(e):
        log.append("ok")

    bus.on(EventType.APP_ERROR, bad_handler)
    bus.on(EventType.APP_ERROR, good_handler)
    bus.publish_type(EventType.APP_ERROR)

    assert log == ["ok"]


def test_publish_type_convenience():
    bus = EventBus()
    received = []
    bus.on(EventType.UI_NOTIFICATION, lambda e: received.append(e.data))
    bus.publish_type(EventType.UI_NOTIFICATION, data={"msg": "hi"}, source="test")
    assert received[0]["msg"] == "hi"
