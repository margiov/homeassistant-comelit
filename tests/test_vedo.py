from typing import ClassVar
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import STATE_OFF, STATE_ON
import pytest

from custom_components.comelit import ComelitVedo
from custom_components.comelit.exception import CookieException
from custom_components.comelit.vedo import SensorUpdater, VedoRequest

VEDO = "custom_components.comelit.vedo"


@pytest.fixture
def vedo():
    vedo_instance = ComelitVedo(
        host="127.0.0.1",
        port=80,
        password="pwd",
        scan_interval=30,
        expose_bin_sensors=True,
    )
    vedo_instance.binary_sensor_add_entities = Mock()
    vedo_instance.alarm_add_entities = Mock()
    return vedo_instance


@pytest.fixture
def vedo_instance():
    return ComelitVedo(
        host="127.0.0.1",
        port=80,
        password="pwd",
        scan_interval=30,
        expose_bin_sensors=True,
    )


def make_response(status_code=200, content=b"", headers=None, text=""):
    response = Mock()
    response.status_code = status_code
    response.content = content
    response.headers = headers or {}
    response.text = text
    return response


@pytest.mark.asyncio
async def test_vedo_sensor(hass):
    vedo_instance = ComelitVedo(
        host="127.0.0.1",
        port=80,
        password="pwd",
        scan_interval=30,
        expose_bin_sensors=True,
    )
    vedo_instance.binary_sensor_add_entities = lambda *args, **kwargs: None

    sensor_dict = {"index": 1, "id": 1, "name": "garage", "status": "0011"}
    vedo_instance.update_sensor(sensor_dict)

    assert len(vedo_instance.sensors) == 1


def test_start_starts_the_updater(vedo):
    vedo.vedo_updater = Mock()
    vedo.start()
    vedo.vedo_updater.start.assert_called_once()


def test_build_http_without_query(vedo):
    url, headers = vedo.build_http(None, "cookie", VedoRequest.ZONE_STAT)
    assert url.startswith("http://127.0.0.1:80/user/zone_stat.json?_=")
    assert headers["Cookie"] == "cookie"
    assert headers["X-Requested-With"] == "XMLHttpRequest"


def test_build_http_with_query(vedo):
    url, headers = vedo.build_http({"A": "b"}, None, "user/foo.json?bar=1")
    assert url.startswith("http://127.0.0.1:80/user/foo.json?bar=1&_=")
    assert headers["A"] == "b"
    assert "Cookie" not in headers


def test_get_returns_json(vedo):
    response = make_response(content=b'{"status": "0,1"}')
    with patch(f"{VEDO}.requests.get", return_value=response) as get:
        assert vedo.get("uid", VedoRequest.ZONE_STAT, True) == {"status": "0,1"}
    get.assert_called_once()
    response.raise_for_status.assert_called_once()


def test_get_returns_raw_text(vedo):
    response = make_response(content=b"ok")
    with patch(f"{VEDO}.requests.get", return_value=response):
        assert vedo.get("uid", VedoRequest.ACTION, False) == b"ok"


def test_post(vedo):
    response = make_response()
    with patch(f"{VEDO}.requests.post", return_value=response) as post:
        assert vedo.post("http://url", {"a": 1}, {}) is response
    post.assert_called_once()


def test_login_returns_cookie(vedo):
    response = make_response(headers={"set-cookie": "uid=1"})
    with (
        patch.object(vedo, "post", return_value=response) as post,
        patch.object(vedo, "get", return_value={"logged": 1}),
    ):
        assert vedo.login() == "uid=1"
    assert post.call_args.args[1] == {"code": "pwd"}


def test_login_without_cookie_raises(vedo):
    response = make_response()
    with (
        patch.object(vedo, "post", return_value=response),
        pytest.raises(Exception, match="Unable to obtain the cookie"),
    ):
        vedo.login()


def test_login_bad_status_returns_none(vedo):
    response = make_response(status_code=204)
    with patch.object(vedo, "post", return_value=response):
        assert vedo.login() is None


def test_logout(vedo):
    with patch.object(vedo, "post") as post:
        vedo.logout(None)
        post.assert_not_called()

        vedo.logout("uid")
        assert post.call_args.args[1] == {"logout": 1}

        post.side_effect = OSError("boom")
        vedo.logout("uid")  # errors are ignored


@pytest.mark.parametrize(
    ("method", "key"),
    [("arm", "tot"), ("arm_night", "p1"), ("disarm", "dis")],
)
def test_arm_disarm_actions(vedo, method, key):
    with (
        patch.object(vedo, "login", return_value="uid"),
        patch.object(vedo, "post") as post,
        patch.object(vedo, "logout") as logout,
        patch(f"{VEDO}.time.sleep"),
    ):
        getattr(vedo, method)(3)

    post.assert_called_once()
    url, params, _headers = post.call_args.args
    assert url == "http://127.0.0.1:80/action.cgi"
    assert params == {
        "forced": 1,
        "vedo_param": 1,
        "type_param": key,
        "area_param": 3,
    }
    logout.assert_called_once_with("uid")


def test_arm_disarm_retries_then_gives_up(vedo):
    with (
        patch.object(vedo, "login", side_effect=OSError("down")) as login,
        patch(f"{VEDO}.time.sleep") as sleep,
    ):
        vedo.arm(1)

    assert login.call_count == 5
    assert sleep.call_count == 5


def test_update_sensor(vedo):
    vedo.update_sensor(None)
    assert vedo.sensors == {}

    vedo.update_sensor({"id": 1, "name": "garage", "status": "0001"})
    sensor = vedo.sensors[1]
    assert sensor.is_on
    vedo.binary_sensor_add_entities.assert_called_once()

    sensor.schedule_update_ha_state = Mock()
    vedo.update_sensor({"id": 1, "name": "garage", "status": "0000"})
    assert sensor.state == STATE_OFF
    sensor.schedule_update_ha_state.assert_called_once()

    vedo.update_sensor({"id": 2})  # malformed data is logged, not raised
    assert 2 not in vedo.sensors


AREA_FLAGS = {"alarm": 0, "sabotage": 0, "anomaly": 0, "out_time": 0}


@pytest.mark.parametrize(
    ("armed", "expected"),
    [
        (4, AlarmControlPanelState.ARMED_AWAY),
        (1, AlarmControlPanelState.ARMED_NIGHT),
        (0, AlarmControlPanelState.DISARMED),
    ],
)
def test_update_area(vedo, armed, expected):
    vedo.update_area({"id": 0, "name": "home", "armed": armed, **AREA_FLAGS})
    assert vedo.areas[0].state == expected


def test_update_area_updates_existing(vedo):
    vedo.update_area({"id": 0, "name": "home", "armed": 0, **AREA_FLAGS})
    area = vedo.areas[0]
    area.schedule_update_ha_state = Mock()

    vedo.update_area({"id": 0, "name": "home", "armed": 4, **AREA_FLAGS})
    assert area.state == AlarmControlPanelState.ARMED_AWAY
    vedo.alarm_add_entities.assert_called_once()

    vedo.update_area({"id": 1})  # malformed data is logged, not raised
    assert 1 not in vedo.areas


ZONE_DESC = {"description": ["door", "window"], "in_area": [1, 0]}
ZONE_STAT = {"status": "0001,0000"}
AREA_DESC = {
    "description": ["home"],
    "present": [1],
    "p1_pres": [1],
    "p2_pres": [0],
}
AREA_STAT = {
    "ready": [1],
    "armed": [4],
    "alarm": [0],
    "alarm_memory": [0],
    "sabotage": [0],
    "anomaly": [0],
    "in_time": [0],
    "out_time": [0],
}


def run_once(updater, responses, iterations=1):
    """Run the given number of polling iterations of the updater."""
    vedo = updater._vedo
    sleeps = []

    def stop(*args):
        sleeps.append(args)
        if len(sleeps) == iterations:
            updater._active = False

    vedo.get = Mock(side_effect=responses)
    with patch(f"{VEDO}.time.sleep", side_effect=stop):
        updater.run()


def test_updater_polls_sensors_and_areas(vedo):
    updater = SensorUpdater("test", 1, vedo)
    vedo.login = Mock(return_value="uid")

    run_once(updater, [ZONE_DESC, ZONE_STAT, AREA_DESC, AREA_STAT])

    assert list(vedo.sensors) == [0]
    assert vedo.sensors[0].state == STATE_ON
    assert vedo.areas[0].state == AlarmControlPanelState.ARMED_AWAY
    assert updater._uid == "uid"


def test_updater_logs_out_on_expired_cookie(vedo):
    updater = SensorUpdater("test", 1, vedo)
    vedo.login = Mock(return_value="uid")
    vedo.logout = Mock()

    expired = {"description": ["door"], "in_area": ["Not logged"]}
    run_once(updater, [expired, {"status": "0"}, AREA_DESC, AREA_STAT])

    vedo.logout.assert_called_once_with("uid")
    assert updater._uid is None


def test_updater_logs_out_on_inconsistent_data(vedo):
    updater = SensorUpdater("test", 1, vedo)
    vedo.login = Mock(return_value="uid")
    vedo.logout = Mock()

    run_once(updater, [ZONE_DESC, {"status": "0"}, AREA_DESC, AREA_STAT])

    vedo.logout.assert_called_once_with("uid")
    assert vedo.sensors == {}


def test_updater_retries_failed_login(vedo):
    updater = SensorUpdater("test", 1, vedo)
    vedo.login = MagicMock(side_effect=[None, "uid"])

    run_once(updater, [ZONE_DESC, ZONE_STAT, AREA_DESC, AREA_STAT], iterations=2)

    assert vedo.login.call_count == 2
    assert vedo.get.call_count == 4


def test_updater_logout_without_vedo():
    updater = SensorUpdater("test", 1, None)
    updater._uid = "uid"
    updater.logout()
    assert updater._uid is None


def test_cookie_exception_is_an_exception():
    assert issubclass(CookieException, Exception)


class TestBuildHttp:
    def test_cgi_path_has_no_cache_buster(self, vedo_instance):
        url, _ = vedo_instance.build_http({}, None, VedoRequest.LOGIN)
        assert url == "http://127.0.0.1:80/login.cgi"

    def test_json_path_gets_cache_buster(self, vedo_instance):
        url, _ = vedo_instance.build_http({}, None, VedoRequest.ZONE_STAT)
        assert url.startswith("http://127.0.0.1:80/user/zone_stat.json?_=")

    def test_json_path_with_query_appends_cache_buster(self, vedo_instance):
        url, _ = vedo_instance.build_http({}, None, "user/foo.json?bar=1")
        assert url.startswith("http://127.0.0.1:80/user/foo.json?bar=1&_=")


class TestParseResponse:
    def test_valid_payload_is_returned(self, vedo_instance):
        result = vedo_instance._parse_response(b'{"logged": 1, "status": "0000"}')
        assert result == {"logged": 1, "status": "0000"}

    def test_payload_without_logged_field_is_returned(self, vedo_instance):
        result = vedo_instance._parse_response(b'{"status": "0000"}')
        assert result == {"status": "0000"}

    def test_malformed_json_raises_cookie_exception(self, vedo_instance):
        # The panel returns broken JSON (e.g. `["Not logged]`) when the
        # session is invalid instead of a clean error payload.
        with pytest.raises(CookieException):
            vedo_instance._parse_response(b'{"ready": ["Not logged]}')

    def test_negative_logged_field_raises_cookie_exception(self, vedo_instance):
        with pytest.raises(CookieException):
            vedo_instance._parse_response(b'{"logged": -8, "status": "Not logged"}')


class TestLogin:
    def _mock_post_response(self, vedo_instance, status_code=200, cookie="uid=abc"):
        response = mock.MagicMock()
        response.status_code = status_code
        response.headers = {"set-cookie": cookie} if cookie else {}
        response.text = ""
        vedo_instance.post = mock.MagicMock(return_value=response)

    def test_login_succeeds_when_session_is_valid(self, vedo_instance):
        self._mock_post_response(vedo_instance)
        vedo_instance.get = mock.MagicMock(return_value={"logged": 1})

        assert vedo_instance.login() == "uid=abc"

    def test_login_raises_when_panel_rejects_credentials(self, vedo_instance):
        # 200 + a cookie, but the panel never actually authenticated the
        # session: the credentials/session check must catch this.
        self._mock_post_response(vedo_instance)
        vedo_instance.get = mock.MagicMock(
            side_effect=CookieException("invalid session (logged=-8)")
        )

        with pytest.raises(CookieException):
            vedo_instance.login()

    def test_login_returns_none_on_bad_http_status(self, vedo_instance):
        self._mock_post_response(vedo_instance, status_code=500)

        assert vedo_instance.login() is None

    def test_login_raises_when_no_cookie_is_returned(self, vedo_instance):
        self._mock_post_response(vedo_instance, cookie=None)

        with pytest.raises(Exception, match="Unable to obtain the cookie"):
            vedo_instance.login()


class TestArmDisarm:
    def test_arm_disarm_posts_expected_params(self, vedo_instance):
        vedo_instance.login = mock.MagicMock(return_value="cookie")
        vedo_instance.logout = mock.MagicMock()
        vedo_instance.post = mock.MagicMock()

        vedo_instance.arm_disarm("tot", 2)

        url, params, headers = vedo_instance.post.call_args[0]
        assert url == "http://127.0.0.1:80/action.cgi"
        assert params == {
            "forced": 1,
            "vedo_param": 1,
            "type_param": "tot",
            "area_param": 2,
        }
        assert headers["Cookie"] == "cookie"
        vedo_instance.logout.assert_called_once_with("cookie")


class TestUpdateArea:
    BASE_AREA: ClassVar = {
        "id": 1,
        "name": "Ingresso",
        "armed": 0,
        "alarm": 0,
        "sabotage": 0,
        "anomaly": 0,
        "out_time": 0,
    }

    def _update(self, vedo_instance, **overrides):
        area = {**self.BASE_AREA, **overrides}
        vedo_instance.update_area(area)
        return vedo_instance.areas[area["id"]].update_state.call_args[0][0]

    def _vedo_with_area(self, vedo_instance):
        vedo_instance.alarm_add_entities = lambda entities: None
        vedo_instance.update_area({**self.BASE_AREA})
        vedo_instance.areas[1] = mock.MagicMock()
        return vedo_instance

    def test_disarmed(self, vedo_instance):
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=0) == AlarmControlPanelState.DISARMED

    def test_armed_away(self, vedo_instance):
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=4) == AlarmControlPanelState.ARMED_AWAY

    def test_armed_night(self, vedo_instance):
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=1) == AlarmControlPanelState.ARMED_NIGHT

    def test_arming(self, vedo_instance):
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=4, out_time=1) == AlarmControlPanelState.ARMING

    def test_triggered(self, vedo_instance):
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=4, alarm=1) == AlarmControlPanelState.TRIGGERED

    def test_unknown_armed_value_does_not_raise(self, vedo_instance, caplog):
        # "armed" values other than 1/4 (e.g. a partial P2 arm) used to hit no
        # branch and raise UnboundLocalError on the undefined `state`.
        vedo = self._vedo_with_area(vedo_instance)
        assert self._update(vedo, armed=2) == AlarmControlPanelState.ARMED_CUSTOM_BYPASS
        assert "Error updating the alarm area" not in caplog.text


class TestSensorUpdaterAreaFiltering:
    def test_only_present_areas_are_updated(self, vedo_instance):
        vedo_instance.expose_bin_sensors = False
        vedo_instance.login = mock.MagicMock(return_value="cookie")
        vedo_instance.update_area = mock.MagicMock()

        def fake_get(uid, path, is_response):
            if path == VedoRequest.ZONE_DESC:
                return {"description": ["Zone 1"], "in_area": [0]}
            if path == VedoRequest.ZONE_STAT:
                return {"status": "0000"}
            if path == VedoRequest.AREA_DESC:
                return {
                    "description": ["Area 1", "Area 2"],
                    "present": [1, 0],
                    "p1_pres": [0, 0],
                    "p2_pres": [0, 0],
                }
            if path == VedoRequest.AREA_STAT:
                return {
                    "ready": [1, 1],
                    "armed": [0, 0],
                    "alarm": [0, 0],
                    "alarm_memory": [0, 0],
                    "sabotage": [0, 0],
                    "anomaly": [0, 0],
                    "in_time": [0, 0],
                    "out_time": [0, 0],
                }
            raise AssertionError(f"unexpected path {path}")

        vedo_instance.get = mock.MagicMock(side_effect=fake_get)

        updater = SensorUpdater("Thread#BS", 30, vedo_instance)

        def stop_after_one_iteration(*args, **kwargs):
            updater._active = False

        with mock.patch("custom_components.comelit.vedo.time.sleep") as sleep_mock:
            sleep_mock.side_effect = stop_after_one_iteration
            updater._active = True
            updater.run()

        assert vedo_instance.update_area.call_count == 1
        assert vedo_instance.update_area.call_args[0][0]["name"] == "Area 1"
