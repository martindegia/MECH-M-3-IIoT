import requests

BASE_URL = "http://192.168.50.121:8080"


def test_get_endpoint():
    response = requests.get(f"{BASE_URL}", timeout=2)

    assert response.status_code == 200
    assert response.json()["broker_port"] == 1883


def test_post_endpoint():
    payload = {"reading_interval_seconds": 60}

    response = requests.post(
        f"{BASE_URL}",
        json=payload,
        timeout=2,
    )

    assert response.status_code == 200

    response = requests.get(f"{BASE_URL}", timeout=2)
    assert response.json()["reading_interval_seconds"] == 60
