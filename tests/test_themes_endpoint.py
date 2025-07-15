import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module


@pytest.fixture
def client():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    models.init_db()
    with app_module.app.test_client() as client:
        yield client


def test_themes_endpoint_lists_css_files(client):
    resp = client.get('/themes')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert 'light' in data
    assert 'dark' in data
    assert 'base' not in data
