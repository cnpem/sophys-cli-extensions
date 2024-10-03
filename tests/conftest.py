import pathlib

import pytest


@pytest.fixture
def test_data_location():
    return str(pathlib.Path(__file__).parent / "test_data") + '/'
