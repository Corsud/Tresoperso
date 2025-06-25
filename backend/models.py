from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
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

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))

    category = relationship('Category', back_populates='transactions')


def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(engine)

    # Create a default user if none exists
    session = SessionLocal()
    if not session.query(User).first():
        user = User(username='admin', password=generate_password_hash('admin'))
        session.add(user)
        session.commit()
    session.close()
