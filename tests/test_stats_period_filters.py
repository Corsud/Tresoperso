import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module

from tests.test_period_utils import get_period_dates


class FixedDate(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2021, 1, 15)


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    models.init_db()
    session = models.SessionLocal()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 10), label='before-week', amount=100),
        models.Transaction(date=datetime.date(2021, 1, 12), label='week-1', amount=10),
        models.Transaction(date=datetime.date(2021, 1, 16), label='week-2', amount=-5),
        models.Transaction(date=datetime.date(2021, 1, 20), label='after-week', amount=20),
        models.Transaction(date=datetime.date(2021, 2, 1), label='next-month', amount=40),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_stats_current_week(client):
    login(client)
    today = datetime.date(2021, 1, 15)
    start, end = get_period_dates('current-week', today)
    resp = client.get(f'/stats?start_date={start}&end_date={end}')
    assert resp.status_code == 200
    data = {d['month']: d['total'] for d in resp.get_json()}
    assert data == {'2021-01': 5}


def test_stats_current_month(client):
    login(client)
    today = datetime.date(2021, 1, 15)
    start, end = get_period_dates('current-month', today)
    resp = client.get(f'/stats?start_date={start}&end_date={end}')
    assert resp.status_code == 200
    data = {d['month']: d['total'] for d in resp.get_json()}
    assert data == {'2021-01': 125}
