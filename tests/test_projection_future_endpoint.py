import pytest
from sqlalchemy import create_engine, inspect
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


def test_projection_future_crud(client):
    login(client)
    # initially empty
    resp = client.get('/projection/future')
    assert resp.status_code == 200
    assert resp.get_json() == {'rows': []}

    # create rows
    rows = [
        {'category': 'Food', 'sign': 'expense', 'values': [1, 2], 'custom': False},
        {'category': 'Salary', 'sign': 'income', 'values': [3, 4], 'custom': True},
    ]
    resp = client.post('/projection/future', json={'rows': rows})
    assert resp.status_code == 201
    assert 'ids' in resp.get_json()

    resp = client.get('/projection/future')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['rows']) == 2
    assert data['rows'][0]['category'] == 'Food'

    # update
    rows[0]['values'] = [5, 6]
    resp = client.put('/projection/future', json={'rows': rows})
    assert resp.status_code == 200

    resp = client.get('/projection/future')
    data = resp.get_json()
    assert data['rows'][0]['values'][0] == 5

    # delete
    resp = client.delete('/projection/future')
    assert resp.status_code == 200
    resp = client.get('/projection/future')
    assert resp.get_json()['rows'] == []


def test_init_db_creates_table():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    models.init_db()
    insp = inspect(engine)
    assert insp.has_table('projection_rows')
