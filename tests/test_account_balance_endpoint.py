import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module

@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', datetime.datetime)
    models.init_db()
    session = models.SessionLocal()
    acc = models.BankAccount(account_type='Compte', number='123')
    session.add(acc)
    session.commit()
    acc_id = acc.id
    session.close()
    with app_module.app.test_client() as client:
        client.acc_id = acc_id
        yield client

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200

def test_invalid_initial_balance_returns_error(client):
    login(client)
    resp = client.put(f'/accounts/{client.acc_id}/balance', json={'initial_balance': 'oops'})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid balance'}
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(client.acc_id)
    session.close()
    assert acc.initial_balance == 0

def test_invalid_balance_date_returns_error(client):
    login(client)
    resp = client.put(
        f'/accounts/{client.acc_id}/balance',
        json={'balance_date': '2021-13-01'},
    )
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid balance'}
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(client.acc_id)
    session.close()
    assert acc.balance_date is None

def test_update_balance_success(client):
    login(client)
    resp = client.put(
        f'/accounts/{client.acc_id}/balance',
        json={'initial_balance': '12.5', 'balance_date': '2021-06-01'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['initial_balance'] == 12.5
    assert data['balance_date'] == '2021-06-01'
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(client.acc_id)
    session.close()
    assert acc.initial_balance == 12.5
    assert acc.balance_date == datetime.date(2021, 6, 1)
