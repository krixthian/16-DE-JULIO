from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from enum import Enum

class RolEnum(str, Enum):
    admin = 'Admin'
    director = 'Director'
    docente = 'Docente'
    orientador = 'Orientador'

# --- Schemas de Usuario ---
class UsuarioBase(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    rol: RolEnum = RolEnum.docente

class UsuarioCreate(UsuarioBase):
    password: Optional[str] = None

class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[EmailStr] = None
    rol: Optional[RolEnum] = None
    activo: Optional[bool] = None
    password: Optional[str] = None

class UsuarioResponse(UsuarioBase):
    id: int
    activo: bool
    requiere_cambio_password: bool = False

    class Config:
        from_attributes = True

# --- Schemas de Autenticación ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator('new_password')
    @classmethod
    def validate_password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña admite como máximo 72 bytes UTF-8.')
        return value
