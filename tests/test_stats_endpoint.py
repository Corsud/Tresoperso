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
        models.Transaction(date=datetime.date(2021, 1, 10), label='T1', amount=100),
        models.Transaction(date=datetime.date(2021, 1, 20), label='T2', amount=-40),
        models.Transaction(date=datetime.date(2021, 2, 5), label='T3', amount=50),
        models.Transaction(date=datetime.date(2021, 3, 3), label='T4', amount=-10),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_stats_no_filters(client):
    login(client)
    resp = client.get('/stats')
    assert resp.status_code == 200
    data = {d['month']: d['total'] for d in resp.get_json()}
    assert data == {'2021-01': 60, '2021-02': 50, '2021-03': -10}


def test_stats_start_date_filter(client):
    login(client)
    resp = client.get('/stats?start_date=2021-02-01')
    assert resp.status_code == 200
    data = {d['month']: d['total'] for d in resp.get_json()}
    assert data == {'2021-02': 50, '2021-03': -10}


def test_stats_end_date_filter(client):
    login(client)
    resp = client.get('/stats?end_date=2021-02-28')
    assert resp.status_code == 200
    data = {d['month']: d['total'] for d in resp.get_json()}
    assert data == {'2021-01': 60, '2021-02': 50}
