from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator, field_validator, StringConstraints
from typing import Optional, Annotated
from enum import Enum

class RolEnum(str, Enum):
    admin = 'Admin'
    director = 'Director'
    docente = 'Docente'
    orientador = 'Orientador'

# --- Schemas de Usuario ---
class UsuarioBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nombre: str = Field(min_length=1,max_length=100)
    apellido: str = Field(min_length=1,max_length=100)
    email: EmailStr = Field(max_length=254)
    rol: RolEnum = RolEnum.docente

class UsuarioCreate(UsuarioBase):
    password: Annotated[str,StringConstraints(strip_whitespace=False)] = Field(min_length=1)

    @field_validator('password')
    @classmethod
    def password_length(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña no puede superar 72 bytes.')
        return value

class UsuarioUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True,extra='forbid')
    nombre: Optional[str] = Field(default=None,min_length=1,max_length=100)
    apellido: Optional[str] = Field(default=None,min_length=1,max_length=100)
    email: Optional[EmailStr] = Field(default=None,max_length=254)
    rol: Optional[RolEnum] = None
    activo: Optional[bool] = None
    password: Optional[Annotated[str,StringConstraints(strip_whitespace=False)]] = Field(default=None,min_length=1)

    @model_validator(mode='after')
    def supplied_fields(self):
        if any(getattr(self,k) is None for k in self.model_fields_set):
            raise ValueError('Los campos enviados no pueden ser nulos.')
        if self.password is not None:
            UsuarioCreate.password_length(self.password)
        return self

class UsuarioResponse(UsuarioBase):
    id: int
    activo: bool

    class Config:
        from_attributes = True

# --- Schemas de Autenticación ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
