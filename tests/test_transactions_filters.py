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
    cat1 = models.Category(name='Food', color='red')
    sub1 = models.Subcategory(name='Meal', category=cat1, color='red')
    cat2 = models.Category(name='Salary', color='blue')
    sub2 = models.Subcategory(name='Job', category=cat2, color='blue')
    session.add_all([
        cat1, sub1, cat2, sub2,
        models.Transaction(
            date=datetime.date(2021, 1, 1), label='T1', amount=10,
            favorite=True, reconciled=True, to_analyze=True,
            category=cat1, subcategory=sub1,
        ),
        models.Transaction(
            date=datetime.date(2021, 1, 2), label='T2', amount=20,
            favorite=False, reconciled=False, to_analyze=False,
            category=cat2, subcategory=sub2,
        ),
    ])
    session.commit()
    cat1_id, sub1_id = cat1.id, sub1.id
    cat2_id, sub2_id = cat2.id, sub2.id
    session.close()
    with app_module.app.test_client() as client:
        client.cat1_id = cat1_id
        client.sub1_id = sub1_id
        client.cat2_id = cat2_id
        client.sub2_id = sub2_id
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


def test_filter_account_none(client):
    login(client)
    session = models.SessionLocal()
    acc = models.BankAccount(account_type='Compte', number='999')
    session.add(acc)
    session.flush()
    acc_id = acc.id
    session.add(models.Transaction(date=datetime.date(2021, 1, 3), label='T3', amount=5, bank_account_id=acc_id))
    session.commit()
    session.close()

    resp = client.get('/transactions?account_none=true')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert all(t['account_id'] is None for t in data)

    resp = client.get(f'/transactions?account_id={acc_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['account_id'] == acc_id


def test_filter_category_and_subcategory(client):
    login(client)
    resp = client.get(
        f'/transactions?category_id={client.cat1_id}&subcategory_id={client.sub1_id}'
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['label'] == 'T1'


def test_filter_category_only(client):
    login(client)
    resp = client.get(f'/transactions?category_id={client.cat2_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['label'] == 'T2'


def test_filter_subcategory_only(client):
    login(client)
    resp = client.get(f'/transactions?subcategory_id={client.sub2_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['label'] == 'T2'
