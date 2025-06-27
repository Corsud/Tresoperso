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


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_accounts_requires_login(client):
    resp = client.get('/accounts')
    assert resp.status_code == 401


def test_accounts_returns_accounts(client):
    login(client)
    resp = client.get('/accounts')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['number'] == '123'


def test_create_account(client):
    login(client)
    resp = client.post('/accounts', json={'name': 'New', 'account_type': 'Compte', 'number': '999'})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['number'] == '999'


def test_update_account(client):
    login(client)
    # first create
    resp = client.post('/accounts', json={'name': 'Tmp', 'account_type': 'Compte', 'number': '888'})
    acc_id = resp.get_json()['id']
    # update
    resp = client.put(f'/accounts/{acc_id}', json={'name': 'Updated', 'number': '777'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Updated'
    assert data['number'] == '777'


def test_delete_account(client):
    login(client)
    resp = client.post('/accounts', json={'name': 'Tmp', 'account_type': 'Compte', 'number': '555'})
    acc_id = resp.get_json()['id']
    resp = client.delete(f'/accounts/{acc_id}')
    assert resp.status_code == 204
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(acc_id)
    session.close()
    assert acc is None
