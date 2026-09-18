from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import secrets
from sqlalchemy.exc import IntegrityError
from core.mail import mail_settings, send_temporary_password, MailError

import models, schemas
from database import get_db
from core.security import get_password_hash
from api.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Usuarios"])

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
    
    temporary = user.rol == 'Docente'
    if not temporary and not user.password:
        raise HTTPException(status_code=422, detail='La contraseña es obligatoria para este rol.')
    if not temporary and len(user.password.encode('utf-8')) > 72:
        raise HTTPException(status_code=422, detail='La contraseña excede el tamaño permitido.')
    try:
        settings = mail_settings() if temporary else None
        password = secrets.token_urlsafe(18) if temporary else user.password
        new_user = models.Usuario(
            nombre=user.nombre, apellido=user.apellido, email=user.email, rol=user.rol,
            password_hash=get_password_hash(password), requiere_cambio_password=temporary,
            password_temporal_vence_en=datetime.utcnow() + timedelta(hours=24) if temporary else None,
        )
        db.add(new_user)
        db.flush()
        if temporary:
            send_temporary_password(user.email, password, settings)
        db.commit()
    except MailError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='El correo ya está registrado.') from None
    db.refresh(new_user)
    return new_user


@router.post('/{user_id}/resend-temporary-password')
def resend_temporary_password(user_id: int, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    user = db.query(models.Usuario).filter(models.Usuario.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    if not user.activo or not user.requiere_cambio_password:
        raise HTTPException(status_code=409, detail='Solo se reenvía el acceso de usuarios activos con cambio pendiente.')
    try:
        settings = mail_settings()
        password = secrets.token_urlsafe(18)
        user.password_hash = get_password_hash(password)
        user.password_temporal_vence_en = datetime.utcnow() + timedelta(hours=24)
        user.credencial_version += 1
        db.flush()
        send_temporary_password(user.email, password, settings)
        db.commit()
    except MailError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return {'message':'El servidor de correo aceptó el envío de una nueva contraseña temporal.'}

@router.get("/", response_model=List[schemas.UsuarioResponse])
def get_users(db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    return db.query(models.Usuario).all()

@router.put("/{user_id}", response_model=schemas.UsuarioResponse)
def update_user(user_id: int, user: schemas.UsuarioUpdate, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).with_for_update().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = user.model_dump(exclude_unset=True)
    if 'password' in update_data:
        if db_user.rol == 'Docente' or update_data.get('rol') == 'Docente' or db_user.requiere_cambio_password:
            raise HTTPException(status_code=422, detail='La contraseña del docente debe establecerla el propio docente.')
        password = update_data.pop('password')
        if not password or len(password.encode('utf-8')) > 72:
            raise HTTPException(status_code=422, detail='Contraseña no válida.')
        update_data['password_hash'] = get_password_hash(password)
        db_user.credencial_version += 1
    if update_data.get('email', db_user.email) != db_user.email or update_data.get('activo') is False:
        db_user.credencial_version += 1
        
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/{user_id}")
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user: models.Usuario = Depends(check_admin)):
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).with_for_update().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db_user.activo = False
    db.commit()
    return {"message": "Usuario desactivado correctamente"}
