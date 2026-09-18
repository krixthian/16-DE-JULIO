import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
import models
from core.security import get_password_hash

def seed_data():
    print("Conectando a la base de datos...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Comprobar si ya existe un admin
    admin = db.query(models.Usuario).filter(models.Usuario.email == "admin@16dejulio.edu.bo").first()
    
    if not admin:
        print("Creando usuario administrador inicial...")
        hashed_password = get_password_hash("Admin123!")
        nuevo_admin = models.Usuario(
            nombre="Super",
            apellido="Administrador",
            email="admin@16dejulio.edu.bo",
            password_hash=hashed_password,
            rol="Admin"
        )
        db.add(nuevo_admin)
        db.commit()
        print("Administrador creado exitosamente:")
        print("   Correo: admin@16dejulio.edu.bo")
        print("   Clave:  Admin123!")
    else:
        print("El administrador ya existe en la base de datos.")
    
    db.close()

if __name__ == "__main__":
    seed_data()
