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
    cat = models.Category(name='Food', color='red')
    sub = models.Subcategory(name='Meal', category=cat, color='red')
    tx = models.Transaction(
        date=datetime.date(2021, 1, 1),
        label='Lunch',
        amount=-10,
        category=cat,
        subcategory=sub,
    )
    session.add_all([cat, sub, tx])
    session.commit()
    tx_id = tx.id
    cat_id = cat.id
    sub_id = sub.id
    session.close()
    with app_module.app.test_client() as client:
        client.tx_id = tx_id
        client.cat_id = cat_id
        client.sub_id = sub_id
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_put_transaction_invalid_category(client):
    login(client)
    resp = client.put(f'/transactions/{client.tx_id}', json={'category_id': 9999})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid category'}
    session = models.SessionLocal()
    tx = session.query(models.Transaction).get(client.tx_id)
    session.close()
    assert tx.category_id == client.cat_id


def test_put_transaction_invalid_subcategory(client):
    login(client)
    resp = client.put(
        f'/transactions/{client.tx_id}', json={'subcategory_id': 9999}
    )
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid category'}
    session = models.SessionLocal()
    tx = session.query(models.Transaction).get(client.tx_id)
    session.close()
    assert tx.subcategory_id == client.sub_id
