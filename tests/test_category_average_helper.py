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


def setup_db(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    app_module.SessionLocal = models.SessionLocal
    monkeypatch.setattr(app_module, 'datetime', FixedDate)
    monkeypatch.setattr(app_module.routes, 'datetime', FixedDate)
    models.init_db()
    return models.SessionLocal()


def test_compute_category_monthly_averages(monkeypatch):
    session = setup_db(monkeypatch)
    food = models.Category(name='Food')
    misc = models.Category(name='Misc')
    session.add_all([food, misc])
    session.flush()
    session.add_all([
        models.Transaction(date=datetime.date(2020, 8, 10), label='t1', amount=10, category=food),
        models.Transaction(date=datetime.date(2020, 9, 5), label='t2', amount=5, category=food, to_analyze=False),
        models.Transaction(date=datetime.date(2021, 2, 20), label='t3', amount=3, category=food),
        models.Transaction(date=datetime.date(2021, 6, 1), label='t4', amount=7, category=misc),
        models.Transaction(date=datetime.date(2021, 7, 1), label='t5', amount=2, category=misc),
    ])
    session.commit()
    avgs = app_module.compute_category_monthly_averages(session)
    assert avgs['Food'] == pytest.approx(13/12)
    assert avgs['Misc'] == pytest.approx(7/12)
    session.close()
