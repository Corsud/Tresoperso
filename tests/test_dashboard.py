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
    assert any(a['label'] == 'Huge expense' for a in data['alerts'])
    first = data['alerts'][0]
    for key in ['date', 'label', 'amount', 'category', 'reason']:
        assert key in first
    favs = {}
    cats = {grp['category']: grp for grp in data['favorite_summaries']}
    for grp in data['favorite_summaries']:
        for itm in grp['items']:
            favs[itm['name']] = itm
    assert 'Shop' in favs
    assert favs['Shop']['current_total'] == -70
    assert 'Food' in favs
    assert 'Food' in cats


def test_dashboard_custom_threshold(client):
    login(client)
    resp = client.get('/dashboard?threshold=10')
    assert resp.status_code == 200
    data = resp.get_json()
    alerts = [a for a in data['alerts'] if a['label'] == 'Huge expense']
    assert alerts and alerts[0]['reason'] == 'income_threshold'


def test_dashboard_favorites_only(client):
    """Dashboard can filter on favorite transactions only."""
    login(client)
    resp = client.get('/dashboard?favorites_only=true')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['favorites_only'] is True
    assert data['alerts'] == []


def test_dashboard_schema(client):
    login(client)
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ['favorite_count', 'recent_total', 'balance_total', 'favorites_only', 'alerts', 'favorite_summaries']:
        assert key in data
    if data['alerts']:
        alert = data['alerts'][0]
        for key in ['date', 'label', 'amount', 'category', 'reason']:
            assert key in alert
    if data['favorite_summaries']:
        grp = data['favorite_summaries'][0]
        assert 'category' in grp and 'items' in grp
        if grp['items']:
            item = grp['items'][0]
            for key in ['type', 'name', 'current_total', 'six_month_avg']:
                assert key in item

