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
        models.Transaction(date=datetime.date(2021,1,1), label='T1', amount=10),
        models.Transaction(date=datetime.date(2021,1,2), label='T2', amount=20)
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_delete_unassigned_transactions(client):
    login(client)
    session = models.SessionLocal()
    acc = models.BankAccount(account_type='Compte', number='123')
    session.add(acc)
    session.flush()
    session.add(models.Transaction(date=datetime.date(2021,1,3), label='T3', amount=5, bank_account_id=acc.id))
    session.commit()
    session.close()

    resp = client.delete('/transactions/unassigned')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['deleted'] == 2
    session = models.SessionLocal()
    remaining = session.query(models.Transaction).count()
    session.close()
    assert remaining == 1

