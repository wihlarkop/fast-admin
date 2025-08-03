"""
Authentication middleware and utilities for Fast-Admin

This module provides authentication and authorization functionality
including session management, password hashing, and permission checking.
"""

import os
import secrets
from datetime import datetime, timedelta, UTC
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from .models import group_permission, permissions, sessions, user_group, user_permission, users


class AuthConfig:
    """Authentication configuration"""

    # Session settings
    SESSION_COOKIE_NAME = "admin_session_id"
    SESSION_EXPIRE_DAYS = 7

    # JWT settings (optional)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = 24

    # Password settings
    PASSWORD_MIN_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL_CHARS = False


class PasswordManager:
    """Password hashing and verification"""

    def __init__(self):
        self.hasher = PasswordHasher()

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return self.hasher.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            self.hasher.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            return False

    def validate_password_strength(self, password: str) -> list[str]:
        """Validate password strength and return list of errors"""
        errors = []

        if len(password) < AuthConfig.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {AuthConfig.PASSWORD_MIN_LENGTH} characters long")

        if AuthConfig.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if AuthConfig.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if AuthConfig.REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")

        if AuthConfig.REQUIRE_SPECIAL_CHARS and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")

        return errors


class SessionManager:
    """
    Manage user sessions with persistent database storage.
    
    Sessions are stored in the database to ensure they persist across server restarts.
    This allows users to remain logged in even after the server is restarted.
    
    Note on datetime handling:
    - All datetime objects created in this class use UTC timezone (timezone-aware)
    - When retrieving datetime objects from the database, they might be timezone-naive
    - We ensure consistent timezone awareness before comparing datetime objects
    - This prevents the "can't compare offset-naive and offset-aware datetimes" error
    """

    def __init__(self, engine: Engine | AsyncEngine):
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)
        # Using database for persistent session storage

    def generate_session_id(self) -> str:
        """Generate a secure session ID"""
        return secrets.token_urlsafe(32)

    async def create_session(self, user_id: int, ip_address: str = None) -> str:
        """Create a new session for user"""
        session_id = self.generate_session_id()
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(days=AuthConfig.SESSION_EXPIRE_DAYS)
        
        # Insert session into database
        insert_query = insert(sessions).values(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            last_activity=now,
            ip_address=ip_address
        )
        
        # Update user's last login
        update_query = update(users).where(
            users.c.id == user_id
        ).values(last_login=now)

        if self.is_async:
            async with self.engine.begin() as conn:
                await conn.execute(insert_query)
                await conn.execute(update_query)
        else:
            with self.engine.begin() as conn:
                conn.execute(insert_query)
                conn.execute(update_query)

        return session_id

    def get_session(self, session_id: str) -> dict | None:
        """Get session data"""
        now = datetime.now(tz=UTC)
        
        # Query session from database
        query = select(sessions).where(sessions.c.session_id == session_id)
        
        try:
            if self.is_async:
                # For async execution, we need to run this in an event loop
                # Since this method is not async, we'll use a synchronous approach
                # that works with both sync and async engines
                with self.engine.connect() as conn:
                    result = conn.execute(query)
                    session_row = result.first()
            else:
                with self.engine.connect() as conn:
                    result = conn.execute(query)
                    session_row = result.first()
            
            if not session_row:
                return None
                
            session = dict(session_row._mapping)
            
            # Ensure datetime objects are timezone-aware
            # This fixes the "can't compare offset-naive and offset-aware datetimes" error
            if session['expires_at'] and not session['expires_at'].tzinfo:
                session['expires_at'] = session['expires_at'].replace(tzinfo=UTC)
            if session['created_at'] and not session['created_at'].tzinfo:
                session['created_at'] = session['created_at'].replace(tzinfo=UTC)
            if session['last_activity'] and not session['last_activity'].tzinfo:
                session['last_activity'] = session['last_activity'].replace(tzinfo=UTC)
            
            # Check if session is expired
            if session['expires_at'] < now:
                self.destroy_session(session_id)
                return None
                
            # Update last activity
            update_query = update(sessions).where(
                sessions.c.session_id == session_id
            ).values(last_activity=now)
            
            if self.is_async:
                with self.engine.begin() as conn:
                    conn.execute(update_query)
            else:
                with self.engine.begin() as conn:
                    conn.execute(update_query)
                    
            # Convert to the expected format
            return {
                'user_id': session['user_id'],
                'created_at': session['created_at'],
                'expires_at': session['expires_at'],
                'ip_address': session['ip_address'],
                'last_activity': now
            }
        except Exception as e:
            print(f"Error retrieving session: {e}")
            return None

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session"""
        try:
            # Delete session from database
            delete_query = delete(sessions).where(sessions.c.session_id == session_id)
            
            if self.is_async:
                with self.engine.begin() as conn:
                    result = conn.execute(delete_query)
                    return result.rowcount > 0
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(delete_query)
                    return result.rowcount > 0
        except Exception as e:
            print(f"Error destroying session: {e}")
            return False

    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            now = datetime.now(tz=UTC)
            
            # Note: We don't need to handle timezone awareness here because
            # the comparison is done at the database level, and SQLAlchemy
            # will handle the conversion appropriately when constructing the SQL query.
            # The issue only occurs when comparing Python datetime objects directly.
            
            # Delete expired sessions from database
            delete_query = delete(sessions).where(sessions.c.expires_at < now)
            
            if self.is_async:
                with self.engine.begin() as conn:
                    conn.execute(delete_query)
            else:
                with self.engine.begin() as conn:
                    conn.execute(delete_query)
                    
            return True
        except Exception as e:
            print(f"Error cleaning up expired sessions: {e}")
            return False


class AuthManager:
    """Main authentication manager"""

    def __init__(self, engine: Engine | AsyncEngine):
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)
        self.password_manager = PasswordManager()
        self.session_manager = SessionManager(engine)
        self.security = HTTPBearer(auto_error=False)

    async def authenticate_user(self, username: str, password: str) -> dict | None:
        """Authenticate a user with username and password"""
        query = select(users).where(
            (users.c.username == username) | (users.c.email == username)
        )

        if self.is_async:
            async with self.engine.begin() as conn:
                result = await conn.execute(query)
                user_row = result.first()
        else:
            with self.engine.begin() as conn:
                result = conn.execute(query)
                user_row = result.first()

        if not user_row:
            return None

        user_data = dict(user_row._mapping)

        # Check if user is active
        if not user_data.get('is_active', False):
            return None

        # Verify password
        if not self.password_manager.verify_password(password, user_data['password_hash']):
            return None

        # Remove sensitive data
        user_data.pop('password_hash', None)
        return user_data

    async def get_user_permissions(self, user_id: int) -> list[str]:
        """Get all permissions for a user (direct and through groups)"""
        permissions_list = []

        # Direct user permissions
        direct_perms_query = select(permissions.c.codename).select_from(
            permissions.join(user_permission, permissions.c.id == user_permission.c.permission_id)
        ).where(user_permission.c.user_id == user_id)

        # Group permissions
        group_perms_query = select(permissions.c.codename).select_from(
            permissions
            .join(group_permission, permissions.c.id == group_permission.c.permission_id)
            .join(user_group, group_permission.c.group_id == user_group.c.group_id)
        ).where(user_group.c.user_id == user_id)

        if self.is_async:
            async with self.engine.begin() as conn:
                # Get direct permissions
                result = await conn.execute(direct_perms_query)
                permissions_list.extend([row[0] for row in result])

                # Get group permissions
                result = await conn.execute(group_perms_query)
                permissions_list.extend([row[0] for row in result])
        else:
            with self.engine.begin() as conn:
                # Get direct permissions
                result = conn.execute(direct_perms_query)
                permissions_list.extend([row[0] for row in result])

                # Get group permissions
                result = conn.execute(group_perms_query)
                permissions_list.extend([row[0] for row in result])

        return list(set(permissions_list))  # Remove duplicates

    async def has_permission(self, user_id: int, permission: str) -> bool:
        """Check if user has a specific permission"""
        user_permissions = await self.get_user_permissions(user_id)
        return permission in user_permissions or 'admin.*' in user_permissions

    def create_access_token(self, user_data: dict) -> str:
        """Create JWT access token"""
        to_encode = {
            'sub': str(user_data['id']),
            'username': user_data['username'],
            'email': user_data['email'],
            'is_staff': user_data.get('is_staff', False),
            'is_superuser': user_data.get('is_superuser', False),
            'exp': datetime.now(tz=UTC) + timedelta(hours=AuthConfig.JWT_EXPIRE_HOURS)
        }

        return jwt.encode(to_encode, AuthConfig.JWT_SECRET_KEY, algorithm=AuthConfig.JWT_ALGORITHM)

    def verify_access_token(self, token: str) -> dict | None:
        """Verify and decode JWT access token"""
        try:
            payload = jwt.decode(token, AuthConfig.JWT_SECRET_KEY, algorithms=[AuthConfig.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None


class AdminAuthMiddleware:
    """Authentication middleware for admin routes"""

    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager

    async def __call__(self, request: Request, call_next):
        """Middleware to check authentication for admin routes"""
        # Skip auth for login/logout pages and static files
        if (request.url.path.startswith('/admin/login') or
            request.url.path.startswith('/admin/logout') or
            request.url.path.startswith('/static') or
            not request.url.path.startswith('/admin')):
            response = await call_next(request)
            return response

        # Check session-based auth
        session_id = request.cookies.get(AuthConfig.SESSION_COOKIE_NAME)
        user = None

        if session_id:
            session_data = self.auth_manager.session_manager.get_session(session_id)
            if session_data:
                user = await self.get_user_by_id(session_data['user_id'])

        # Check JWT auth as fallback
        if not user:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                payload = self.auth_manager.verify_access_token(token)
                if payload:
                    user = await self.get_user_by_id(int(payload['sub']))

        if not user:
            # Redirect to login page
            return RedirectResponse(url='/admin/login', status_code=302)

        # Add user to request state
        request.state.user = user
        response = await call_next(request)
        return response

    async def get_user_by_id(self, user_id: int) -> dict | None:
        """Get user data by ID"""
        query = select(users).where(users.c.id == user_id)

        if self.auth_manager.is_async:
            async with self.auth_manager.engine.begin() as conn:
                result = await conn.execute(query)
                user_row = result.first()
        else:
            with self.auth_manager.engine.begin() as conn:
                result = conn.execute(query)
                user_row = result.first()

        if not user_row:
            return None

        user_data = dict(user_row._mapping)
        user_data.pop('password_hash', None)  # Remove sensitive data
        return user_data


# Dependency functions for FastAPI
async def get_current_user(request: Request) -> dict:
    """Get current authenticated user"""
    if not hasattr(request.state, 'user'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.state.user


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current active user"""
    if not current_user.get('is_active', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_staff_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """Get current staff user"""
    if not current_user.get('is_staff', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_permission(permission: str):
    """Decorator to require specific permission"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request and auth_manager from args/kwargs
            request = None
            auth_manager = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )

            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )

            # Superusers have all permissions
            if user.get('is_superuser', False):
                return await func(*args, **kwargs)

            # Check permission (would need auth_manager instance)
            # For now, just check if user is staff
            if not user.get('is_staff', False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_staff(func):
    """Decorator to require staff privileges"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if not request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found"
            )

        user = getattr(request.state, 'user', None)
        if not user or not user.get('is_staff', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff privileges required"
            )

        return await func(*args, **kwargs)

    return wrapper
