import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend as app_module


@pytest.fixture
def client():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    app_module.SessionLocal = models.SessionLocal
    models.init_db()
    with app_module.app.test_client() as client:
        yield client


def login(client):
    resp = client.post('/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200


def import_file(client, csv):
    data = {'file': (io.BytesIO(csv.encode('utf-8')), 'test.csv')}
    return client.post('/import', data=data, content_type='multipart/form-data')


def test_reimport_returns_duplicates(client):
    login(client)
    csv = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat;-12,34
2021-01-03;Credit;VIR;Salaire;1000,00
"""
    first = import_file(client, csv)
    assert first.status_code == 200
    data1 = first.get_json()
    acc_id = data1['account']['id']
    assert data1.get('imported') == 2
    assert 'duplicates' not in data1

    second = import_file(client, csv)
    assert second.status_code == 200
    data2 = second.get_json()
    assert data2['account']['id'] == acc_id
    assert not data2.get('errors')
    assert 'duplicates' in data2
    assert len(data2['duplicates']) == 2

    session = models.SessionLocal()
    accounts = session.query(models.BankAccount).all()
    session.close()
    assert len(accounts) == 1


def test_import_with_custom_profile(client, monkeypatch):
    login(client)
    csv_body = "Achat;Debit;2021-01-02;-12,34;CB\n"
    csv = "Compte courant 12345678 2021-01-01\n" + csv_body

    mapping = {
        'label': 0,
        'type': 1,
        'date': 2,
        'amount': 3,
        'payment_method': 4,
    }

    original = app_module.routes.parse_csv

    def custom_parse(content):
        return original(content, mapping=mapping)

    monkeypatch.setattr(app_module.routes, 'parse_csv', custom_parse)

    first = import_file(client, csv)
    assert first.status_code == 200
    data1 = first.get_json()
    acc_id = data1['account']['id']
    assert data1.get('imported') == 1
    assert 'duplicates' not in data1

    second = import_file(client, csv)
    assert second.status_code == 200
    data2 = second.get_json()
    assert data2['account']['id'] == acc_id
    assert not data2.get('errors')
    assert 'duplicates' in data2
    assert len(data2['duplicates']) == 1
