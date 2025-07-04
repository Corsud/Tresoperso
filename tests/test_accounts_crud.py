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
    with app_module.app.test_client() as client:
        yield client

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_create_update_delete_account(client):
    login(client)
    # create
    resp = client.post('/accounts', json={'name': 'Main', 'account_type': 'Compte', 'number': '1'})
    assert resp.status_code == 201
    data = resp.get_json()
    acc_id = data['id']
    assert data['name'] == 'Main'

    # update
    resp = client.put(f'/accounts/{acc_id}', json={'name': 'Updated', 'number': '2'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Updated'
    assert data['number'] == '2'

    # delete
    resp = client.delete(f'/accounts/{acc_id}')
    assert resp.status_code == 204
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(acc_id)
    session.close()
    assert acc is None

