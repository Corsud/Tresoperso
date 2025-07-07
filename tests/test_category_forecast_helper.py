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


def test_compute_category_forecast(monkeypatch):
    session = setup_db(monkeypatch)
    food = models.Category(name='Food')
    misc = models.Category(name='Misc')
    session.add_all([food, misc])
    session.flush()
    current_start = datetime.date(2021, 7, 1)
    start = app_module._shift_month(current_start, -12)
    for i in range(12):
        d = app_module._shift_month(start, i)
        session.add_all([
            models.Transaction(
                date=d,
                label=f'f{i}',
                amount=2 * i + 3,
                category=food,
                to_analyze=False if i == 0 else True,
            ),
            models.Transaction(date=d, label=f'm{i}', amount=10, category=misc),
        ])
    session.commit()
    result = app_module.compute_category_forecast(session)
    session.close()
    rows = {r['category']: r['values'] for r in result['rows']}
    assert rows['Food'][0] == pytest.approx(27.5)
    assert rows['Food'][-1] == pytest.approx(50.76923)
    assert all(v == pytest.approx(10) for v in rows['Misc'])
