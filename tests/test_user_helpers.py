from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash

from backend import models


def setup_db():
    engine = create_engine('sqlite:///:memory:')
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    models.init_db()


def test_create_user_hashes_password():
    setup_db()
    models.create_user('bob', 'secret')
    session = models.SessionLocal()
    stored = session.query(models.User).filter_by(username='bob').first()
    session.close()
    assert stored is not None
    assert stored.password != 'secret'
    assert check_password_hash(stored.password, 'secret')


def test_update_user_password_hashes():
    setup_db()
    user = models.create_user('alice', 'oldpw')
    old_hash = user.password
    models.update_user_password(user.id, 'newpw')
    session = models.SessionLocal()
    updated = session.query(models.User).get(user.id)
    session.close()
    assert updated.password != 'newpw'
    assert updated.password != old_hash
    assert check_password_hash(updated.password, 'newpw')
