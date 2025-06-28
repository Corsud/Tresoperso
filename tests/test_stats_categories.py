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
    income = models.Category(name='Income', color='blue')
    food = models.Category(name='Food', color='red')
    mixed = models.Category(name='Mixed', color='green')
    session.add_all([income, food, mixed])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 1), label='inc1', amount=100, category=income),
        models.Transaction(date=datetime.date(2021, 1, 2), label='inc2', amount=50, category=income),
        models.Transaction(date=datetime.date(2021, 1, 3), label='food1', amount=-40, category=food),
        models.Transaction(date=datetime.date(2021, 1, 4), label='food2', amount=-10, category=food),
        models.Transaction(date=datetime.date(2021, 1, 5), label='mix+', amount=20, category=mixed),
        models.Transaction(date=datetime.date(2021, 1, 6), label='mix-', amount=-5, category=mixed),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_stats_categories_mixed(client):
    login(client)
    resp = client.get('/stats/categories')
    assert resp.status_code == 200
    data = resp.get_json()
    cats = {d['name']: d for d in data}
    assert cats['Income']['positive'] == 150
    assert cats['Income']['negative'] == 0
    assert cats['Food']['positive'] == 0
    assert cats['Food']['negative'] == 50
    assert cats['Mixed']['positive'] == 20
    assert cats['Mixed']['negative'] == 5
