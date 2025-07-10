from backend.models import Base, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

# 1. Création/complétion des tables attendues
engine = create_engine('sqlite:///tresoperso.db')
Base.metadata.create_all(engine)

# 2. Ajout d’un utilisateur admin (si besoin, adapte le mot de passe)
Session = sessionmaker(bind=engine)
session = Session()

# Vérifie d’abord si un admin existe déjà
def user_exists(username):
    return session.query(User).filter_by(username=username).first() is not None

if not user_exists("admin"):
    user = User(username="admin", password=generate_password_hash("motdepasse"))
    session.add(user)
    session.commit()
    print("Utilisateur admin créé !")
else:
    print("Utilisateur admin déjà présent.")
