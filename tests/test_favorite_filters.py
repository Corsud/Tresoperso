import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module


class FixedDate(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2021, 5, 15)


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    models.init_db()
    session = models.SessionLocal()
    cat = models.Category(name='Cat')
    session.add(cat)
    tx = models.Transaction(date=datetime.date(2021, 1, 1), label='Test Label', amount=-10, category=cat)
    session.add(tx)
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_dashboard_counts_filtered_transactions(client):
    login(client)

    resp = client.get('/dashboard')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['favorite_count'] == 0

    resp = client.post('/favorite_filters', json={'pattern': 'Test'})
    assert resp.status_code == 201

    resp = client.get('/dashboard')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['favorite_count'] == 1
