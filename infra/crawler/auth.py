"""Crawl4AI server auth adapter using the maintained PyJWT package."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

security = HTTPBearer(auto_error=False)
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(48)
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload['exp'] = datetime.now(timezone.utc) + (expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def verify_token(credentials: HTTPAuthorizationCredentials) -> Dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail='No token provided', headers={'WWW-Authenticate': 'Bearer'})
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=['HS256'], options={'require': ['exp']})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'}) from None


def get_token_dependency(config: Dict):
    if config.get('security', {}).get('jwt_enabled', False):
        configured = os.environ.get('SECRET_KEY', '')
        if len(configured.encode()) < 32:
            raise ValueError('JWT-enabled crawler requires SECRET_KEY of at least 32 bytes')
        def jwt_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
            return verify_token(credentials)
        return jwt_required
    return lambda: None


class TokenRequest(BaseModel):
    email: EmailStr
    api_token: Optional[str] = None
