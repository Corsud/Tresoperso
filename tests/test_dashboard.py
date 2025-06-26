import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend import app as app_module

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
    cat = models.Category(name='Food', favorite=True)
    session.add(cat)
    fil = models.FavoriteFilter(pattern='Shop')
    session.add(fil)
    session.add_all([
        models.Transaction(date=datetime.date(2021,2,5), label='inc1', amount=1000),
        models.Transaction(date=datetime.date(2021,3,5), label='inc2', amount=1200),
        models.Transaction(date=datetime.date(2021,4,5), label='inc3', amount=800),
        models.Transaction(date=datetime.date(2021,4,10), label='Food Apr', amount=-60, category=cat),
        models.Transaction(date=datetime.date(2021,5,10), label='Groceries', amount=-50, category=cat),
        models.Transaction(date=datetime.date(2021,5,12), label='Huge expense', amount=-1200, category=cat),
        models.Transaction(date=datetime.date(2021,5,13), label='Shop now', amount=-70, category=cat),
        models.Transaction(date=datetime.date(2021,3,6), label='Shop old', amount=-30, category=cat),
        models.Transaction(date=datetime.date(2021,2,6), label='Shop older', amount=-40, category=cat),
        models.Transaction(date=datetime.date(2021,4,6), label='Shop old2', amount=-50, category=cat),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_dashboard_alerts_and_summaries(client):
    login(client)
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    data = resp.get_json()
    assert any('Huge expense' in a for a in data['alerts'])
    favs = {f['name']: f for f in data['favorite_summaries']}
    assert 'Shop' in favs
    assert favs['Shop']['current_total'] == -70
    assert 'Food' in favs

