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
    models.init_db()
    session = models.SessionLocal()
    cat = models.Category(name='Sub', color='red')
    session.add(cat)
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2020,12,5), label='Abo 01', amount=-50, category=cat),
        models.Transaction(date=datetime.date(2021,1,5), label='Abo 02', amount=-52, category=cat),
        models.Transaction(date=datetime.date(2021,2,5), label='Abo 03', amount=-48, category=cat),
        models.Transaction(date=datetime.date(2021,1,1), label='Club 01', amount=-20, category=cat),
        models.Transaction(date=datetime.date(2021,2,25), label='Club 02', amount=-21, category=cat),
        models.Transaction(date=datetime.date(2021,1,20), label='Unique 01', amount=-5, category=cat),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_recurrents_endpoint(client):
    login(client)
    resp = client.get('/stats/recurrents?month=2021-05')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    rec = data[0]
    assert rec['day'] == 5
    assert rec['category']['name'] == 'Sub'
    assert len(rec['transactions']) == 3
    for t in rec['transactions']:
        assert all(k in t for k in ['date', 'label', 'amount'])


def test_recurrents_date_variation(client):
    login(client)
    resp = client.get('/stats/recurrents?month=2021-05')
    data = resp.get_json()
    labels = [t['label'] for rec in data for t in rec['transactions']]
    assert 'Club 01' not in labels
