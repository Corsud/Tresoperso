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
    cat_old = models.Category(name='OldCat')
    cat_new = models.Category(name='NewCat')
    sub_old = models.Subcategory(name='OldSub', category=cat_old)
    sub_new = models.Subcategory(name='NewSub', category=cat_new)
    session.add_all([cat_old, cat_new, sub_old, sub_new])
    tx1 = models.Transaction(
        date=datetime.date(2021, 1, 1),
        label='Match this',
        amount=-10,
        category=cat_old,
        subcategory=sub_old,
    )
    tx2 = models.Transaction(
        date=datetime.date(2021, 1, 2),
        label='Match this too',
        amount=-20,
    )
    session.add_all([tx1, tx2])
    session.commit()
    new_cat_id = cat_new.id
    new_sub_id = sub_new.id
    session.close()
    with app_module.app.test_client() as client:
        client.new_cat_id = new_cat_id
        client.new_sub_id = new_sub_id
        yield client

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_post_rule_updates_existing_transactions(client):
    login(client)
    resp = client.post(
        '/rules',
        json={
            'pattern': 'Match',
            'category_id': client.new_cat_id,
            'subcategory_id': client.new_sub_id,
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['updated'] == 2
    session = models.SessionLocal()
    txs = session.query(models.Transaction).order_by(models.Transaction.date).all()
    session.close()
    assert len(txs) == 2
    for tx in txs:
        assert tx.category_id == client.new_cat_id
        assert tx.subcategory_id == client.new_sub_id


def test_put_rule_updates_existing_transactions(client):
    login(client)
    resp = client.post(
        '/rules',
        json={
            'pattern': 'Unused',
            'category_id': client.new_cat_id,
            'subcategory_id': client.new_sub_id,
        },
    )
    assert resp.status_code == 201
    rule_id = resp.get_json()['id']

    resp = client.put(f'/rules/{rule_id}', json={'pattern': 'Match'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['updated'] == 2
    session = models.SessionLocal()
    txs = session.query(models.Transaction).all()
    session.close()
    assert len(txs) == 2
    for tx in txs:
        assert tx.category_id == client.new_cat_id
        assert tx.subcategory_id == client.new_sub_id
