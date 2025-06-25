from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

engine = create_engine('sqlite:///tresoperso.db')
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
    transactions = relationship('Transaction', back_populates='category')
    rules = relationship('Rule', back_populates='category')

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    tx_type = Column(String)
    payment_method = Column(String)
    category_id = Column(Integer, ForeignKey('categories.id'))

    category = relationship('Category', back_populates='transactions')


class Rule(Base):
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True)
    pattern = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)

    category = relationship('Category', back_populates='rules')


def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(engine)

    # Ensure new columns exist when upgrading from older versions
    with engine.connect() as conn:
        info = conn.execute(text('PRAGMA table_info(transactions)')).fetchall()
        cols = {row[1] for row in info}
        if 'tx_type' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN tx_type TEXT'))
        if 'payment_method' not in cols:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN payment_method TEXT'))

    # Create a default user if none exists
    session = SessionLocal()
    if not session.query(User).first():
        user = User(username='admin', password=generate_password_hash('admin'))
        session.add(user)
        session.commit()
    session.close()
