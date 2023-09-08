"""Test API enrollment"""

import requests

def test_enrollment_init(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/init"
    data = {
        "user_management_hash": f"{testdata['user_management_hash']}",
        "work_id": "kukko"
    }
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["work_id"] == "kukko"
    assert response.json()["enroll_str"] is not None
    assert response.json()["success"] is True

def test_already_active_enrollment(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/init"
    data = {
        "user_management_hash": f"{testdata['user_management_hash']}",
        "work_id": "kukko"
    }
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["work_id"] == "kukko"
    assert response.json()["enroll_str"] == ""
    assert response.json()["success"] is False
    assert response.json()["reason"] == "Error. work_id has already active enrollment"

