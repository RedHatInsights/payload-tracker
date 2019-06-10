import pytest
import db


@pytest.fixture
def database(mocker):
    mock_db = mocker.patch.object(db, "init_db")
    return mock_db
