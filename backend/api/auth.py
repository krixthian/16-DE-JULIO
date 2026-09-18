from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

import models, schemas
from database import get_db
from core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

router = APIRouter(prefix="/auth", tags=["Autenticación"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_authenticated_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if user is None:
        raise credentials_exception
    if not user.activo:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    if payload.get('cv', 0) != user.credencial_version:
        raise credentials_exception
    if user.requiere_cambio_password and (not user.password_temporal_vence_en or user.password_temporal_vence_en <= datetime.utcnow()):
        raise HTTPException(status_code=401, detail='La contraseña temporal venció. Solicita al administrador un nuevo envío.')
    return user


def get_current_user(user: models.Usuario = Depends(get_authenticated_user)):
    if user.requiere_cambio_password:
        raise HTTPException(status_code=403, detail='Debes cambiar la contraseña temporal antes de continuar.')
    return user

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()
    
    if not user or not user.password_hash or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.activo:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
        
    if user.requiere_cambio_password and (not user.password_temporal_vence_en or user.password_temporal_vence_en <= datetime.utcnow()):
        raise HTTPException(status_code=401, detail='La contraseña temporal venció. Solicita al administrador un nuevo envío.')

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "rol": user.rol, "cv": user.credencial_version}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UsuarioResponse)
def read_users_me(current_user: models.Usuario = Depends(get_authenticated_user)):
    return current_user


@router.post('/change-password', response_model=schemas.Token)
def change_password(data: schemas.PasswordChange, current_user: models.Usuario = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.id == current_user.id).populate_existing().with_for_update().one()
    if not user.activo or (user.requiere_cambio_password and (not user.password_temporal_vence_en or user.password_temporal_vence_en <= datetime.utcnow())):
        raise HTTPException(status_code=401, detail='El acceso temporal venció o fue desactivado.')
    if not user.password_hash or not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail='La contraseña actual es incorrecta.')
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail='Elige una contraseña diferente de la actual.')
    user.password_hash = get_password_hash(data.new_password)
    user.requiere_cambio_password = False
    user.password_temporal_vence_en = None
    user.credencial_version += 1
    db.commit()
    return {'access_token': create_access_token({'sub':user.email, 'rol':user.rol, 'cv':user.credencial_version}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)), 'token_type':'bearer'}
