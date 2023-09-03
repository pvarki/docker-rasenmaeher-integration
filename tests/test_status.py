"""Tests API get status and set-state (set status)"""

import requests

def test_get_dog_init_status(localmaeher_api):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/status/koira"
    response = requests.get(url, json=None, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "init"

def test_set_dog_new_state(localmaeher_api):
    data = {"state":"new", "work_id": "koira", "work_id_hash":"koira_hash", "permit_str": "PaulinTaikaKaulinOnKaunis_PaulisMagicPinIsBuuutiful!11!1"
    }
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/config/set-state"
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_get_dog_new_status(localmaeher_api):
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/status/koira"
    response = requests.get(url, json=None, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "new"

def test_set_dog_init_state(localmaeher_api):
    data = {"state":"init", "work_id": "koira", "work_id_hash":"koira_hash", "permit_str": "PaulinTaikaKaulinOnKaunis_PaulisMagicPinIsBuuutiful!11!1"
    }
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/config/set-state"
    response = requests.post(url, json=data, headers=None, verify=False)
    print(response.json())
    assert response.status_code == 200
    assert response.json()["success"] is True
