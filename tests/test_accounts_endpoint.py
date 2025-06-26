import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend import app as app_module

@pytest.fixture
def client():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    models.init_db()
    session = models.SessionLocal()
    acc = models.BankAccount(account_type='Compte', number='123', export_date=datetime.date(2021, 1, 1))
    session.add(acc)
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def test_accounts_requires_login(client):
    resp = client.get('/accounts')
    assert resp.status_code == 401


def test_accounts_returns_accounts(client):
    login = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert login.status_code == 200
    resp = client.get('/accounts')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['number'] == '123'
