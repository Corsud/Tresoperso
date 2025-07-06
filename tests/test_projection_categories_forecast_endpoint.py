import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module


class FixedDate(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2021, 7, 15)


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
    food = models.Category(name='Food')
    misc = models.Category(name='Misc')
    session.add_all([food, misc])
    session.flush()
    current_start = datetime.date(2021, 7, 1)
    start = app_module._shift_month(current_start, -12)
    for i in range(12):
        d = app_module._shift_month(start, i)
        session.add_all([
            models.Transaction(date=d, label=f'f{i}', amount=2 * i + 3, category=food),
            models.Transaction(date=d, label=f'm{i}', amount=10, category=misc),
        ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_projection_categories_forecast_endpoint(client):
    login(client)
    resp = client.get('/projection/categories/forecast')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['period'] == '2021-07 to 2022-06'
    rows = {r['category']: r['values'] for r in data['rows']}
    assert rows['Food'][0] == pytest.approx(27)
    assert rows['Food'][-1] == pytest.approx(49)
    assert all(v == pytest.approx(10) for v in rows['Misc'])
