import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module

@pytest.fixture
def client():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    app_module.SessionLocal = models.SessionLocal
    models.init_db()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_import_presets_crud(client):
    login(client)

    resp = client.get('/import_presets')
    assert resp.status_code == 200
    assert resp.get_json() == []

    mapping = {'date': 'Date', 'label': 'Libelle'}
    resp = client.post('/import_presets', json={'name': 'Test', 'mapping': mapping})
    assert resp.status_code == 201
    data = resp.get_json()
    pid = data['id']
    assert data['name'] == 'Test'
    assert data['mapping'] == mapping

    resp = client.get('/import_presets')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1

    resp = client.put(f'/import_presets/{pid}', json={'name': 'Updated'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Updated'

    resp = client.delete(f'/import_presets/{pid}')
    assert resp.status_code == 200

    resp = client.get('/import_presets')
    assert resp.status_code == 200
    assert resp.get_json() == []
