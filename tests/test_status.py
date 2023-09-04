"""Test API get status and set-state (set status)"""

import requests

def test_get_dog_init_status(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/status/{testdata['work_id1']}"
    response = requests.get(url, json=None, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "init"

def test_set_dog_new_state(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/config/set-state"
    data = {
        "state":"new", 
        "work_id": f"{testdata['work_id1']}",
        "work_id_hash":"work_id_hash",
        "permit_str": f"{testdata['permit_str']}"
    }
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_get_dog_new_status(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/status/{testdata['work_id1']}"
    response = requests.get(url, json=None, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "new"

def test_set_dog_init_state(localmaeher_api, testdata):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/config/set-state"
    data = {
        "state":"init", 
        "work_id": f"{testdata['work_id1']}",
        "work_id_hash":"work_id_hash",
        "permit_str": f"{testdata['permit_str']}"
    }
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["success"] is True
