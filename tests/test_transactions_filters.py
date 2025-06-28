import datetime
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
    session = models.SessionLocal()
    session.add_all([
        models.Transaction(date=datetime.date(2021,1,1), label='T1', amount=10, favorite=True, reconciled=True, to_analyze=True),
        models.Transaction(date=datetime.date(2021,1,2), label='T2', amount=20, favorite=False, reconciled=False, to_analyze=False),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_filter_favorite(client):
    login(client)
    resp = client.get('/transactions?favorite=true')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['favorite'] is True

    resp = client.get('/transactions?favorite=false')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['favorite'] is False


def test_filter_reconciled(client):
    login(client)
    resp = client.get('/transactions?reconciled=true')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['reconciled'] is True

    resp = client.get('/transactions?reconciled=false')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['reconciled'] is False


def test_filter_to_analyze(client):
    login(client)
    resp = client.get('/transactions?to_analyze=true')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['to_analyze'] is True

    resp = client.get('/transactions?to_analyze=false')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['to_analyze'] is False

