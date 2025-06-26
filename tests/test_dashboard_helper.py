import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend import app as app_module

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
