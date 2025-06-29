import pytest
import datetime
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
    session.add(cat)
    sub = models.Subcategory(name='Meal', category=cat, color=cat.color)
    session.add(sub)
    session.commit()
    cat_id = cat.id
    sub_id = sub.id
    session.close()
    with app_module.app.test_client() as client:
        client.cat_id = cat_id
        client.sub_id = sub_id
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_put_category_color_updates_subs(client):
    login(client)
    new_color = '#00ff00'
    resp = client.put(f'/categories/{client.cat_id}', json={'color': new_color})
    assert resp.status_code == 200
    session = models.SessionLocal()
    sub = session.query(models.Subcategory).get(client.sub_id)
    session.close()
    assert sub.color == new_color


def test_delete_category_with_subcategory_fails(client):
    login(client)
    resp = client.delete(f'/categories/{client.cat_id}')
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data
    assert 'transactions' in data
    assert data['transactions'] == []
    session = models.SessionLocal()
    cat = session.query(models.Category).get(client.cat_id)
    session.close()
    assert cat is not None


def test_delete_category_without_subcategories(client):
    login(client)
    resp = client.post('/categories', json={'name': 'Temp'})
    assert resp.status_code == 201
    cat_id = resp.get_json()['id']
    resp = client.delete(f'/categories/{cat_id}')
    assert resp.status_code == 200
    session = models.SessionLocal()
    cat = session.query(models.Category).get(cat_id)
    session.close()
    assert cat is None


def test_delete_category_after_removing_sub(client):
    login(client)
    resp = client.delete(f'/subcategories/{client.sub_id}')
    assert resp.status_code == 200
    resp = client.delete(f'/categories/{client.cat_id}')
    assert resp.status_code == 200
    session = models.SessionLocal()
    cat = session.query(models.Category).get(client.cat_id)
    session.close()
    assert cat is None


def test_delete_category_with_transactions_fails(client):
    login(client)
    session = models.SessionLocal()
    cat = session.query(models.Category).get(client.cat_id)
    tx = models.Transaction(
        date=datetime.date(2021, 1, 1),
        label='tx1',
        amount=-10,
        category=cat,
    )
    session.add(tx)
    session.commit()
    session.close()
    resp = client.delete(f'/categories/{client.cat_id}')
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'transactions' in data and len(data['transactions']) == 1
