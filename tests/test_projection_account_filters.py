import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module

class FixedDate(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2021, 7, 15)

@pytest.fixture
def client_with_accounts(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    monkeypatch.setattr(app_module.routes, 'datetime', FixedDate)
    models.init_db()
    session = models.SessionLocal()
    a1 = models.BankAccount(account_type='Compte', number='A1', initial_balance=100)
    a2 = models.BankAccount(account_type='Compte', number='A2', initial_balance=200)
    session.add_all([a1, a2])
    session.flush()
    a1_id = a1.id
    a2_id = a2.id
    session.add_all([
        models.Transaction(date=datetime.date(2021,6,10), label='t1', amount=10, bank_account_id=a1.id),
        models.Transaction(date=datetime.date(2021,6,20), label='t2', amount=-5, bank_account_id=a1.id),
        models.Transaction(date=datetime.date(2021,5,1), label='t3', amount=20, bank_account_id=a2.id),
        models.Transaction(date=datetime.date(2021,7,1), label='t4', amount=-7, bank_account_id=a2.id),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client, a1_id, a2_id

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200

def test_projection_account_filter(client_with_accounts):
    client, a1, a2 = client_with_accounts
    login(client)
    resp = client.get(f'/projection?account_ids={a1}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['total'] == 5  # 10 + (-5)

def test_balance_endpoint(client_with_accounts):
    client, a1, a2 = client_with_accounts
    login(client)
    resp = client.get(f'/balance?date=2021-06-30&account_ids={a1}')
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == pytest.approx(105)
    resp = client.get(f'/balance?date=2021-06-30&account_ids={a1},{a2}')
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == pytest.approx(325)
