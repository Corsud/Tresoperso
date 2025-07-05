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
    acc = models.BankAccount(name='Main', initial_balance=200)
    cat = models.Category(name='Sub', color='red')
    session.add_all([acc, cat])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2020,12,5), label='Abo 01', amount=-50, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,1,5), label='Abo 02', amount=-52, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,2,5), label='Abo 03', amount=-48, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,1,1), label='Club 01', amount=-20, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,2,25), label='Club 02', amount=-21, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,1,20), label='Unique 01', amount=-5, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,5,10), label='Salary', amount=1000, account=acc),
        models.Transaction(date=datetime.date(2021,5,15), label='Groceries', amount=-100, category=cat, account=acc),
        models.Transaction(date=datetime.date(2021,5,20), label='Stuff', amount=-30, category=cat, account=acc),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_recurrents_summary(client):
    login(client)
    resp = client.get('/stats/recurrents/summary?month=2021-05')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['positive'] == pytest.approx(1000)
    assert data['negative'] == pytest.approx(130)
    assert data['balance'] == pytest.approx(874)
    assert data['recurrent'] == pytest.approx(70.5)
