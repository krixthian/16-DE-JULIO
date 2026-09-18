import bcrypt
from datetime import datetime, timedelta, timezone
import os
import secrets
from pathlib import Path
from jose import JWTError, jwt
from typing import Optional

def load_secret():
    configured = os.environ.get('JWT_SECRET_KEY')
    if configured:
        return configured
    path = Path(__file__).resolve().parents[1] / '.jwt-secret'
    if not path.exists():
        try:
            with path.open('x',encoding='utf-8') as file:
                file.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
    return path.read_text(encoding='utf-8').strip()

SECRET_KEY = load_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120 # El token durará 2 horas

def verify_password(plain_password, hashed_password):
    if len(plain_password.encode('utf-8')) > 72:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
