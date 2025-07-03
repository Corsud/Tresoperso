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
    models.init_db()
    session = models.SessionLocal()
    food = models.Category(name='Food')
    misc = models.Category(name='Misc')
    session.add_all([food, misc])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2020, 8, 10), label='t1', amount=10, category=food),
        models.Transaction(date=datetime.date(2020, 9, 5), label='t2', amount=5, category=food),
        models.Transaction(date=datetime.date(2021, 2, 20), label='t3', amount=3, category=food),
        models.Transaction(date=datetime.date(2021, 6, 1), label='t4', amount=7, category=misc),
        models.Transaction(date=datetime.date(2021, 7, 1), label='t5', amount=2, category=misc),
    ])
    session.commit()
    session.close()
    with app_module.app.test_client() as client:
        yield client

def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200

def test_projection_categories(client):
    login(client)
    resp = client.get('/projection/categories')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['period'] == '2020-07 to 2021-06'
    assert data['months'][0] == '2020-07'
    assert data['months'][-1] == '2021-06'
    rows = {r['category']: r['values'] for r in data['rows']}
    assert rows['Food'][0] == 10
    assert rows['Food'][1] == 5
    assert rows['Food'][6] == 3
    assert rows['Misc'][10] == 7
    assert rows['Misc'][11] == 2
