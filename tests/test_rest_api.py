import requests

BASE_URL = "http://192.168.50.121:8080"
TIMEOUT = 2


def test_get_config():
    response = requests.get(f"{BASE_URL}/config", timeout=TIMEOUT)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"

    data = response.json()
    assert data["broker_port"] == 1883


def test_post_config():
    payload = {"reading_interval_seconds": 60}

    response = requests.post(
        f"{BASE_URL}/config",
        json=payload,
        timeout=TIMEOUT,
    )

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"

    # Re-read config from the correct endpoint
    response = requests.get(f"{BASE_URL}/config", timeout=TIMEOUT)

    assert response.status_code == 200
    assert response.json()["reading_interval_seconds"] == 60
