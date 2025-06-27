import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    # temp categories.json
    cat_json = tmp_path / "categories.json"
    cat_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_module, "CATEGORIES_JSON", str(cat_json))
    monkeypatch.setattr(models, "__file__", str(tmp_path / "models.py"))
    models.init_db()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def test_category_options_after_add(client):
    login(client)

    # add a category and subcategory
    resp = client.post('/categories', json={'name': 'NewCat'})
    assert resp.status_code == 201
    cat_id = resp.get_json()['id']

    resp = client.post('/subcategories', json={'name': 'Sub1', 'category_id': cat_id})
    assert resp.status_code == 201
    sub_id = resp.get_json()['id']

    resp = client.get('/category-options')
    assert resp.status_code == 200
    data = resp.get_json()
    cats = {c['name']: c for c in data}
    assert 'NewCat' in cats
    assert cats['NewCat']['id'] == cat_id
    subs = {s['name']: s['id'] for s in cats['NewCat']['subcategories']}
    assert 'Sub1' in subs and subs['Sub1'] == sub_id
