"""Session handling of the Comelit hub: expired tokens and failed logins.

The reply payloads are real answers from a Comelit Hub (firmware in use on
2026-11-06): once the hub drops a session, every request made with the old
token gets ``{"req_result": 1, "message": "invalid token"}`` and the
integration must log in again instead of failing forever.
"""

from unittest.mock import patch

import pytest

from custom_components.comelit import ComelitHub
from custom_components.comelit.hub import RequestType, StatusUpdater

from .test_hub import mock_hub_return

INVALID_TOKEN = {
    "req_type": 0,
    "req_sub_type": -1,
    "seq_id": 0,
    "req_result": 1,
    "message": "invalid token",
}
LOGIN_FAILED = {
    "req_type": 5,
    "req_sub_type": -1,
    "seq_id": 3,
    "req_result": 3,
    "message": "device not present in configuration",
}
ANNOUNCE_OK = {
    "req_type": 13,
    "req_sub_type": -1,
    "seq_id": 1,
    "req_result": 0,
    "agent_type": 0,
    "out_data": [{"agent_id": 1, "descrizione": "Comelit Hub 1"}],
}


@pytest.fixture
def hub():
    with patch("socket.socket", side_effect=mock_hub_return):
        hub = ComelitHub(
            client_name="test",
            hub_serial="00000000",
            hub_host="127.0.0.1",
            hub_user="user",
            hub_password="pwd",
            mqtt_port=1883,
            mqtt_user="user",
            mqtt_password="pwd",
            scan_interval=30,
        )
    hub.sent = []
    hub.publish = hub.sent.append
    return hub


def sent_types(hub):
    return [req["req_type"] for req in hub.sent]


def test_invalid_token_triggers_relogin(hub):
    hub.sessiontoken = "1548018463"
    hub.dispatch(INVALID_TOKEN)
    assert hub.sessiontoken == ""
    assert sent_types(hub) == [RequestType.ANNOUNCE]

    # the announce reply goes on with the login
    hub.dispatch(ANNOUNCE_OK)
    assert sent_types(hub) == [RequestType.ANNOUNCE, RequestType.LOGIN]

    hub.dispatch({"req_type": 5, "req_result": 0, "sessiontoken": "42"})
    assert hub.sessiontoken == "42"


def test_burst_of_invalid_tokens_logs_in_once(hub):
    hub.sessiontoken = "1548018463"
    for _ in range(5):
        hub.dispatch(INVALID_TOKEN)
    assert sent_types(hub) == [RequestType.ANNOUNCE]


def test_failed_login_keeps_no_token(hub):
    hub.sessiontoken = "old"
    hub.dispatch(LOGIN_FAILED)
    assert hub.sessiontoken == ""
    assert hub.sent == []


def test_login_reply_without_token_is_ignored(hub):
    hub.sessiontoken = ""
    hub.dispatch({"req_type": 5, "req_result": 0})
    assert hub.sessiontoken == ""


def test_other_errors_do_not_reach_handlers(hub):
    hub.sessiontoken = "valid"
    with patch.object(hub, "status") as status:
        hub.dispatch({"req_type": 0, "req_result": 2, "message": "busy"})
    status.assert_not_called()
    assert hub.sessiontoken == "valid"
    assert hub.sent == []


def test_status_thread_retries_login_without_spinning(hub):
    """With no token the thread sleeps and periodically re-announces."""
    thread = StatusUpdater("test", 30, hub)
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            raise StopIteration

    with (
        patch("custom_components.comelit.hub.time.sleep", side_effect=fake_sleep),
        pytest.raises(StopIteration),
    ):
        thread.run()

    assert sleeps == [1, 1, 1]
    # first iteration retries at once, then waits LOGIN_RETRY_INTERVAL
    assert sent_types(hub) == [RequestType.ANNOUNCE]
