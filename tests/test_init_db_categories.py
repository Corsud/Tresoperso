import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend import models


def test_init_db_syncs_categories(tmp_path, monkeypatch):
    data = {
        "CatA": ["Sub1", "Sub2"],
        "CatB": []
    }
    (tmp_path / "categories.json").write_text(json.dumps(data), encoding="utf-8")

    # configure in-memory DB
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)

    # patch path so init_db reads from our temp categories.json
    monkeypatch.setattr(models, "__file__", str(tmp_path / "models.py"))

    models.init_db()
    session = models.SessionLocal()
    cats = {c.name: [s.name for s in c.subcategories] for c in session.query(models.Category).all()}
    session.close()
    assert cats == {"CatA": ["Sub1", "Sub2"], "CatB": []}
