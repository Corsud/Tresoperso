import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
import backend.routes as routes_module


def setup_db():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    routes_module.models.engine = engine
    routes_module.models.SessionLocal = models.SessionLocal
    models.init_db()
    return models.SessionLocal()


def test_digits_only_vary(monkeypatch):
    session = setup_db()
    cat = models.Category(name='Sub')
    session.add(cat)
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 5), label='Abo 01', amount=-10, category=cat),
        models.Transaction(date=datetime.date(2021, 2, 5), label='Abo 02', amount=-11, category=cat),
        models.Transaction(date=datetime.date(2021, 3, 5), label='Abo 03', amount=-9, category=cat),
    ])
    session.commit()

    recs = routes_module.compute_recurrents(
        session,
        datetime.date(2021, 1, 1),
        datetime.date(2021, 4, 1),
    )

    assert len(recs) == 1
    assert len(recs[0]['transactions']) == 3
    session.close()


def test_date_in_label(monkeypatch):
    session = setup_db()
    cat = models.Category(name='Sub')
    session.add(cat)
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2021, 1, 10), label='Bill 2021-01-01', amount=-40, category=cat),
        models.Transaction(date=datetime.date(2021, 2, 10), label='Bill 2021-02-01', amount=-41, category=cat),
        models.Transaction(date=datetime.date(2021, 3, 10), label='Bill 2021-03-01', amount=-39, category=cat),
    ])
    session.commit()

    recs = routes_module.compute_recurrents(
        session,
        datetime.date(2021, 1, 1),
        datetime.date(2021, 4, 1),
    )

    assert len(recs) == 1
    assert len(recs[0]['transactions']) == 3
    session.close()
