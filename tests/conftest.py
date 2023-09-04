"""The conftest.py provides fixtures for the entire directory. Fixtures defined can be used by any test in that package without needing to import them."""
import pytest

@pytest.fixture
def localmaeher_api():
    return "https://localmaeher.pvarki.fi:4439/api", "v1"

@pytest.fixture
def localhost_api():
    return "http://127.0.0.1:8000/api", "v1"

@pytest.fixture
def openapi_version():
    # OpenAPI version, FastAPI version
    return "3.1.0", "0.1.0"

@pytest.fixture
def testdata():
    return {
        "permit_str": "PaulinTaikaKaulinOnKaunis_PaulisMagicPinIsBuuutiful!11!1",
        "work_id1": "koira",
        "work_id2": "kissa",
    }
