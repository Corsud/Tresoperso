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


def send_preset_file(client, csv):
    data = {'file': (io.BytesIO(csv.encode('utf-8')), 'test.csv')}
    return client.post('/import/preset', data=data, content_type='multipart/form-data')


def test_import_preset_returns_columns_and_preview(client):
    login(client)
    csv = "Date,Libelle,Montant\n2021-01-02,Achat,-12.34\n2021-01-03,Test,5.00\n"
    resp = send_preset_file(client, csv)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['columns'] == ['Date', 'Libelle', 'Montant']
    assert data['preview'][0] == ['2021-01-02', 'Achat', '-12.34']
    assert len(data['preview']) == 2
    session = models.SessionLocal()
    assert session.query(models.Transaction).count() == 0
    session.close()

