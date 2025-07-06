import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module

class FixedDate(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2021, 5, 15)

@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    monkeypatch.setattr(app_module.routes, 'datetime', FixedDate)
    models.init_db()
    session = models.SessionLocal()
    cat1 = models.Category(name='Sub1', color='red')
    cat2 = models.Category(name='Sub2', color='blue')
    session.add_all([cat1, cat2])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2020,12,5), label='Abo1', amount=-50, category=cat1),
        models.Transaction(date=datetime.date(2021,1,5), label='Abo2', amount=-52, category=cat1),
        models.Transaction(date=datetime.date(2021,2,5), label='Abo3', amount=-48, category=cat1),
        models.Transaction(date=datetime.date(2021,1,10), label='Gym1', amount=-25, category=cat2),
        models.Transaction(date=datetime.date(2021,2,10), label='Gym2', amount=-25, category=cat2),
        models.Transaction(date=datetime.date(2021,3,10), label='Gym3', amount=-25, category=cat2),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_recurrents_categories(client):
    login(client)
    resp = client.get('/stats/recurrents/categories?month=2021-05')
    assert resp.status_code == 200
    data = {row['category']: row['total'] for row in resp.get_json()}
    assert data['Sub1'] == pytest.approx(50)
    assert data['Sub2'] == pytest.approx(25)
