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
    cat = models.Category(name='Parent', color='blue')
    session.add(cat)
    session.commit()
    cat_id = cat.id
    session.close()
    with app_module.app.test_client() as client:
        client.cat_id = cat_id
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_post_subcategory_inherits_color(client):
    login(client)
    resp = client.post('/subcategories', json={'name': 'Child', 'category_id': client.cat_id})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['color'] == 'blue'
    sub_id = data['id']
    session = models.SessionLocal()
    sub = session.query(models.Subcategory).get(sub_id)
    session.close()
    assert sub.color == 'blue'
