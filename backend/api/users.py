from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

import models, schemas
from database import get_db
from core.security import get_password_hash
from api.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Usuarios"])

def persist_user(db, user):
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'El correo ya está registrado o una relación impide el cambio.')
    return user

# Solo un admin debería poder gestionar usuarios
def check_admin(current_user: models.Usuario = Depends(get_current_user)):
    if current_user.rol != "Admin":
        raise HTTPException(status_code=403, detail="Privilegios insuficientes")
    return current_user

@router.post("/", response_model=schemas.UsuarioResponse)
def create_user(user: schemas.UsuarioCreate, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    db_user = db.query(models.Usuario).filter(models.Usuario.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.Usuario(
        nombre=user.nombre,
        apellido=user.apellido,
        email=user.email,
        rol=user.rol,
        password_hash=hashed_password
    )
    db.add(new_user)
    return persist_user(db,new_user)

@router.get("/", response_model=List[schemas.UsuarioResponse])
def get_users(db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    return db.query(models.Usuario).all()

@router.put("/{user_id}", response_model=schemas.UsuarioResponse)
def update_user(user_id: int, user: schemas.UsuarioUpdate, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = user.model_dump(exclude_unset=True)
    if user_id == current_user.id and (update_data.get('activo') is False or ('rol' in update_data and update_data['rol'] != 'Admin')):
        raise HTTPException(409, 'No puedes desactivar tu propia cuenta ni quitarte el rol de administrador.')
    if 'email' in update_data and db.query(models.Usuario).filter(models.Usuario.email == update_data['email'],models.Usuario.id != user_id).first():
        raise HTTPException(409, 'El correo ya está registrado')
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
        
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    return persist_user(db,db_user)

@router.delete("/{user_id}")
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    if user_id == current_user.id:
        raise HTTPException(409, 'No puedes desactivar tu propia cuenta de administrador.')
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db_user.activo = False
    db.commit()
    return {"message": "Usuario desactivado correctamente"}
