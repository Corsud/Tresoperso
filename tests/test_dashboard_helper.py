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


def setup_db(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    monkeypatch.setattr(app_module.routes, 'datetime', FixedDate)
    models.init_db()
    return models.SessionLocal()


def test_compute_dashboard_averages(monkeypatch):
    session = setup_db(monkeypatch)
    cat = models.Category(name='Food')
    session.add(cat)
    session.add_all([
        models.Transaction(date=datetime.date(2021,2,5), label='inc1', amount=1000),
        models.Transaction(date=datetime.date(2021,3,5), label='inc2', amount=1200),
        models.Transaction(date=datetime.date(2021,4,5), label='inc3', amount=800),
        models.Transaction(date=datetime.date(2021,4,10), label='t1', amount=-60, category=cat),
        models.Transaction(date=datetime.date(2021,5,10), label='t2', amount=-40, category=cat),
    ])
    session.commit()
    cat_avgs, income_avg = app_module.compute_dashboard_averages(session)
    assert round(cat_avgs[cat.id], 2) == 50
    assert income_avg == pytest.approx(1000)
    session.close()


def test_compute_dashboard_averages_custom_months(monkeypatch):
    """Income average honors the months parameter."""
    session = setup_db(monkeypatch)
    cat = models.Category(name='Food')
    session.add(cat)
    session.add_all([
        models.Transaction(date=datetime.date(2021, 2, 5), label='inc1', amount=1000),
        models.Transaction(date=datetime.date(2021, 3, 5), label='inc2', amount=1200),
        models.Transaction(date=datetime.date(2021, 4, 5), label='inc3', amount=800),
        models.Transaction(date=datetime.date(2021, 4, 10), label='t1', amount=-60, category=cat),
        models.Transaction(date=datetime.date(2021, 5, 10), label='t2', amount=-40, category=cat),
    ])
    session.commit()
    _, income_avg = app_module.compute_dashboard_averages(session, months=1)
    assert income_avg == pytest.approx(800)
    session.close()


def test_compute_dashboard_averages_favorites_only(monkeypatch):
    session = setup_db(monkeypatch)
    cat = models.Category(name='Food')
    session.add(cat)
    session.add_all([
        models.Transaction(date=datetime.date(2021, 2, 5), label='inc1', amount=1000, favorite=False),
        models.Transaction(date=datetime.date(2021, 3, 5), label='inc2', amount=1200, favorite=True),
        models.Transaction(date=datetime.date(2021, 4, 5), label='inc3', amount=800, favorite=False),
        models.Transaction(date=datetime.date(2021, 4, 10), label='t1', amount=-60, category=cat, favorite=False),
        models.Transaction(date=datetime.date(2021, 5, 10), label='t2', amount=-40, category=cat, favorite=True),
    ])
    session.commit()
    cat_avgs, income_avg = app_module.compute_dashboard_averages(session, favorites_only=True)
    assert cat_avgs[cat.id] == pytest.approx(40)
    assert income_avg == pytest.approx(400)
    session.close()
