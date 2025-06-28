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
    cat_inc = models.Category(name='Income')
    sub_inc = models.Subcategory(name='Salary', category=cat_inc)
    cat_food = models.Category(name='Food')
    sub_food = models.Subcategory(name='Groceries', category=cat_food)
    cat_mixed = models.Category(name='Mixed')
    sub_mixed = models.Subcategory(name='Both', category=cat_mixed)
    session.add_all([cat_inc, sub_inc, cat_food, sub_food, cat_mixed, sub_mixed])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 1), label='inc1', amount=100, category=cat_inc, subcategory=sub_inc),
        models.Transaction(date=datetime.date(2021, 1, 2), label='inc2', amount=50, category=cat_inc, subcategory=sub_inc),
        models.Transaction(date=datetime.date(2021, 1, 3), label='food1', amount=-40, category=cat_food, subcategory=sub_food),
        models.Transaction(date=datetime.date(2021, 1, 4), label='food2', amount=-10, category=cat_food, subcategory=sub_food),
        models.Transaction(date=datetime.date(2021, 1, 5), label='mix+', amount=20, category=cat_mixed, subcategory=sub_mixed),
        models.Transaction(date=datetime.date(2021, 1, 6), label='mix-', amount=-5, category=cat_mixed, subcategory=sub_mixed),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_stats_sankey_signs(client):
    login(client)
    resp = client.get('/stats/sankey')
    assert resp.status_code == 200
    data = resp.get_json()
    # Income
    income_rows = [d for d in data if d['source'] == 'Income' and d['target'] == 'Salary']
    assert any(d['sign'] == 1 and d['value'] == 150 for d in income_rows)
    # Expense
    food_rows = [d for d in data if d['source'] == 'Food' and d['target'] == 'Groceries']
    assert any(d['sign'] == -1 and d['value'] == 50 for d in food_rows)
    # Mixed category should have both
    mixed_inc = next(d for d in data if d['source'] == 'Mixed' and d['sign'] == 1)
    mixed_exp = next(d for d in data if d['source'] == 'Mixed' and d['sign'] == -1)
    assert mixed_inc['value'] == 20
    assert mixed_exp['value'] == 5
