from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    Boolean,
    ForeignKey,
    JSON,
    text,
    event,
    inspect,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from flask_login import UserMixin
from werkzeug.security import generate_password_hash
import os
import json

from . import config

engine = create_engine(config.DATABASE_URI)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Ensure SQLite enforces foreign key constraints."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(UserMixin, Base):
    """Simple user account."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default='')
    favorite = Column(Boolean, default=False)
    transactions = relationship(
        'Transaction',
        back_populates='category',
        cascade='all, delete-orphan',
    )
    rules = relationship(
        'Rule',
        back_populates='category',
        cascade='all, delete-orphan',
    )
    favorite_filters = relationship(
        'FavoriteFilter',
        back_populates='category',
        cascade='all, delete-orphan',
    )
    subcategories = relationship(
        'Subcategory',
        back_populates='category',
        cascade='all, delete-orphan',
    )

class Subcategory(Base):
    __tablename__ = 'subcategories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    color = Column(String, default='')
    favorite = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)

    category = relationship('Category', back_populates='subcategories')
    transactions = relationship('Transaction', back_populates='subcategory')

class BankAccount(Base):
    __tablename__ = 'bank_accounts'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default='')
    account_type = Column(String)
    number = Column(String)
    export_date = Column(Date)
    initial_balance = Column(Float, default=0)
    balance_date = Column(Date)

    transactions = relationship(
        'Transaction',
        back_populates='account',
        cascade='all, delete-orphan'
    )

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    tx_type = Column(String)
    payment_method = Column(String)
    bank_account_id = Column(Integer, ForeignKey('bank_accounts.id', ondelete='CASCADE'))
    favorite = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'))
    reconciled = Column(Boolean, default=False)
    to_analyze = Column(Boolean, default=True)

    category = relationship('Category', back_populates='transactions')
    subcategory = relationship('Subcategory', back_populates='transactions')
    account = relationship('BankAccount', back_populates='transactions')


class Rule(Base):
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True)
    pattern = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'))

    category = relationship('Category', back_populates='rules')
    subcategory = relationship('Subcategory')


class FavoriteFilter(Base):
    __tablename__ = 'favorite_filters'

    id = Column(Integer, primary_key=True)
    pattern = Column(String, default='')
    category_id = Column(Integer, ForeignKey('categories.id'))
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'))

    category = relationship('Category', back_populates='favorite_filters')
    subcategory = relationship('Subcategory')


class ProjectionRow(Base):
    __tablename__ = 'projection_rows'

    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False, default='')
    sign = Column(String, nullable=False)
    values = Column(JSON, nullable=False)
    account_ids = Column(String)
    custom = Column(Boolean, default=False)


def init_db():
    """Create database tables if they do not exist."""
    with engine.connect() as conn:
        conn.execute(text('PRAGMA foreign_keys=ON'))
    Base.metadata.create_all(engine)
    if not inspect(engine).has_table('projection_rows'):
        ProjectionRow.__table__.create(bind=engine)

    # Ensure new columns exist when upgrading from older versions
    with engine.connect() as conn:
        info = conn.execute(text('PRAGMA table_info(transactions)')).fetchall()
        cols = {row[1] for row in info}
        if 'tx_type' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN tx_type TEXT'))
        if 'payment_method' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN payment_method TEXT'))
        if 'subcategory_id' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN subcategory_id INTEGER'))
        if 'reconciled' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN reconciled INTEGER DEFAULT 0'))
        if 'to_analyze' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN to_analyze INTEGER DEFAULT 1'))
        if 'bank_account_id' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN bank_account_id INTEGER'))
        if 'favorite' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN favorite INTEGER DEFAULT 0'))

        info = conn.execute(text('PRAGMA table_info(categories)')).fetchall()
        cols = {row[1] for row in info}
        if 'color' not in cols:
            conn.execute(text('ALTER TABLE categories ADD COLUMN color TEXT'))
        if 'favorite' not in cols:
            conn.execute(text('ALTER TABLE categories ADD COLUMN favorite INTEGER DEFAULT 0'))

        info = conn.execute(text('PRAGMA table_info(subcategories)')).fetchall()
        cols = {row[1] for row in info}
        if 'favorite' not in cols:
            conn.execute(text('ALTER TABLE subcategories ADD COLUMN favorite INTEGER DEFAULT 0'))

        info = conn.execute(text('PRAGMA table_info(rules)')).fetchall()
        cols = {row[1] for row in info}
        if 'subcategory_id' not in cols:
            conn.execute(text('ALTER TABLE rules ADD COLUMN subcategory_id INTEGER'))

        info = conn.execute(text('PRAGMA table_info(bank_accounts)')).fetchall()
        cols = {row[1] for row in info}
        if 'name' not in cols:
            conn.execute(text("ALTER TABLE bank_accounts ADD COLUMN name TEXT DEFAULT '' NOT NULL"))
        if 'initial_balance' not in cols:
            conn.execute(text('ALTER TABLE bank_accounts ADD COLUMN initial_balance REAL DEFAULT 0'))
        if 'balance_date' not in cols:
            conn.execute(text('ALTER TABLE bank_accounts ADD COLUMN balance_date DATE'))

    # Create a default user if none exists
    session = SessionLocal()
    if not session.query(User).first():
        user = User(username='admin', password=generate_password_hash('admin'))
        session.add(user)
        session.commit()

    # Synchronize categories and subcategories from categories.json
    path = config.CATEGORIES_JSON
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for cat_name, subcats in data.items():
            cat = session.query(Category).filter_by(name=cat_name).first()
            if not cat:
                cat = Category(name=cat_name)
                session.add(cat)
                session.flush()  # ensure cat.id is available
            for sub_name in subcats:
                exists = (
                    session.query(Subcategory)
                    .filter_by(name=sub_name, category_id=cat.id)
                    .first()
                )
                if not exists:
                    session.add(Subcategory(name=sub_name, category_id=cat.id))
        session.commit()

    session.close()


def create_user(username, password, session=None):
    """Create a user with a hashed password and return the User instance."""
    # Passwords are hashed using PBKDF2-SHA256 with a 16 byte salt
    close = False
    if session is None:
        session = SessionLocal()
        close = True
    user = User(
        username=username,
        password=generate_password_hash(
            password, method="pbkdf2:sha256", salt_length=16
        ),
    )
    session.add(user)
    session.commit()
    # Reload to avoid detached attributes when session closes
    session.refresh(user)
    if close:
        session.close()
    return user


def update_user_password(user_id, password, session=None):
    """Update an existing user's password using a hashed value."""
    # Use the same PBKDF2-SHA256 algorithm and salt length for consistency
    close = False
    if session is None:
        session = SessionLocal()
        close = True
    user = session.query(User).get(user_id)
    if not user:
        if close:
            session.close()
        return None
    user.password = generate_password_hash(
        password, method="pbkdf2:sha256", salt_length=16
    )
    session.commit()
    if close:
        session.close()
    return user
