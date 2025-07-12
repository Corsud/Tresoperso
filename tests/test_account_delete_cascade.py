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
    acc = models.BankAccount(account_type='Compte', number='42')
    session.add(acc)
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 1), label='T1', amount=1, bank_account_id=acc.id),
        models.Transaction(date=datetime.date(2021, 1, 2), label='T2', amount=2, bank_account_id=acc.id)
    ])
    session.commit()
    acc_id = acc.id
    session.close()
    with app_module.app.test_client() as client:
        client.acc_id = acc_id
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_delete_account_removes_transactions(client):
    login(client)
    session = models.SessionLocal()
    initial = session.query(models.Transaction).count()
    session.close()
    assert initial == 2

    resp = client.delete(f'/accounts/{client.acc_id}')
    assert resp.status_code == 204

    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(client.acc_id)
    remaining = session.query(models.Transaction).count()
    session.close()
    assert acc is None
    assert remaining == 0
