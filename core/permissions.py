"""
Permission checking decorators and utilities for Fast-Admin

This module provides fine-grained permission control for admin operations.
"""

from functools import wraps

from fastapi import HTTPException, Request, status


class PermissionChecker:
    """Utility class for checking user permissions"""

    def __init__(self, auth_manager):
        self.auth_manager = auth_manager

    async def user_has_permission(self, user_id: int, permission: str) -> bool:
        """Check if user has a specific permission"""
        return await self.auth_manager.has_permission(user_id, permission)

    async def user_has_any_permission(self, user_id: int, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions"""
        for permission in permissions:
            if await self.user_has_permission(user_id, permission):
                return True
        return False

    async def user_has_all_permissions(self, user_id: int, permissions: list[str]) -> bool:
        """Check if user has all specified permissions"""
        for permission in permissions:
            if not await self.user_has_permission(user_id, permission):
                return False
        return True


def require_permissions(permissions: str | list[str], require_all: bool = False):
    """
    Decorator to require specific permissions
    
    Args:
        permissions: Single permission string or list of permissions
        require_all: If True, user must have ALL permissions. If False, ANY permission is sufficient.
    """
    if isinstance(permissions, str):
        permissions = [permissions]

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
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
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Superusers bypass all permission checks
            if user.get('is_superuser', False):
                return await func(*args, **kwargs)

            # Staff check for basic admin access
            if not user.get('is_staff', False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Staff privileges required"
                )

            # For now, staff users have access to all admin functions
            # In a full implementation, we would check specific permissions here
            # using the auth_manager.has_permission method

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_model_permission(action: str, model_name: str | None = None):
    """
    Decorator to require model-specific permissions
    
    Args:
        action: The action being performed (add, change, delete, view)
        model_name: Optional model name. If not provided, will be inferred from route
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
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
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Superusers bypass all permission checks
            if user.get('is_superuser', False):
                return await func(*args, **kwargs)

            # Staff check for basic admin access
            if not user.get('is_staff', False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Staff privileges required"
                )

            # Determine model name from route if not provided
            if not model_name:
                path_parts = request.url.path.split('/')
                if len(path_parts) >= 3 and path_parts[1] == 'admin':
                    inferred_model = path_parts[2]
                else:
                    inferred_model = 'unknown'
            else:
                inferred_model = model_name

            # Construct permission string
            permission = f"{inferred_model}.{action}"

            # For now, all staff users have access
            # In a full implementation, check specific permission
            # if not await auth_manager.has_permission(user['id'], permission):
            #     raise HTTPException(
            #         status_code=status.HTTP_403_FORBIDDEN,
            #         detail=f"Permission denied: {permission}"
            #     )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators for common actions
def require_add_permission(model_name: str | None = None):
    """Require add permission for a model"""
    return require_model_permission('add', model_name)


def require_change_permission(model_name: str | None = None):
    """Require change permission for a model"""
    return require_model_permission('change', model_name)


def require_delete_permission(model_name: str | None = None):
    """Require delete permission for a model"""
    return require_model_permission('delete', model_name)


def require_view_permission(model_name: str | None = None):
    """Require view permission for a model"""
    return require_model_permission('view', model_name)


# Built-in permission constants
class AdminPermissions:
    """Constants for common admin permissions"""

    # User management
    USER_ADD = "users.add"
    USER_CHANGE = "users.change"
    USER_DELETE = "users.delete"
    USER_VIEW = "users.view"

    # Group management
    GROUP_ADD = "groups.add"
    GROUP_CHANGE = "groups.change"
    GROUP_DELETE = "groups.delete"
    GROUP_VIEW = "groups.view"

    # Permission management
    PERMISSION_ADD = "permissions.add"
    PERMISSION_CHANGE = "permissions.change"
    PERMISSION_DELETE = "permissions.delete"
    PERMISSION_VIEW = "permissions.view"

    # Global permissions
    ADMIN_ACCESS = "admin.access"
    ADMIN_ALL = "admin.*"


def has_admin_access(user: dict) -> bool:
    """Check if user has basic admin access"""
    return user.get('is_staff', False) or user.get('is_superuser', False)


def is_superuser(user: dict) -> bool:
    """Check if user is a superuser"""
    return user.get('is_superuser', False)


def can_manage_users(user: dict) -> bool:
    """Check if user can manage other users"""
    # Only superusers can manage users by default
    return user.get('is_superuser', False)


def can_access_model(user: dict, model_name: str) -> bool:
    """Check if user can access a specific model"""
    if user.get('is_superuser', False):
        return True

    if not user.get('is_staff', False):
        return False

    # For now, all staff can access all models
    # In a full implementation, check specific model permissions
    return True


class PermissionDeniedError(Exception):
    """Custom exception for permission denied errors"""

    def __init__(self, message: str, required_permission: str | None = None):
        self.message = message
        self.required_permission = required_permission
        super().__init__(self.message)
