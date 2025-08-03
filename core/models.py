"""
Built-in authentication and authorization models for Fast-Admin.

This module defines the core tables required for the admin system:
- users: User accounts
- groups: User groups for organizing permissions
- permissions: Individual permissions
- user_group: Many-to-many relationship between users and groups
- group_permission: Many-to-many relationship between groups and permissions
- user_permission: Direct user permissions (optional, for fine-grained control)
"""

from datetime import datetime, UTC

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint

# Metadata instance for all auth tables
metadata = MetaData()

# Users table
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(150), nullable=False, unique=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(128), nullable=False),
    Column("first_name", String(30), nullable=True),
    Column("last_name", String(150), nullable=True),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("is_staff", Boolean, nullable=False, default=False),
    Column("is_superuser", Boolean, nullable=False, default=False),
    Column("date_joined", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    Column("last_login", DateTime, nullable=True),
)

# Groups table
groups = Table(
    "groups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(150), nullable=False, unique=True),
    Column("description", Text, nullable=True),
    Column("created_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
)

# Permissions table
permissions = Table(
    "permissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("codename", String(100), nullable=False),
    Column("content_type", String(100), nullable=False),  # e.g., "users", "products"
    Column("description", Text, nullable=True),
    Column("created_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    UniqueConstraint("codename", "content_type", name="unique_permission_per_content"),
)

# User-Group many-to-many relationship
user_group = Table(
    "user_group",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
    Column("assigned_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    UniqueConstraint("user_id", "group_id", name="unique_user_group"),
)

# Group-Permission many-to-many relationship
group_permission = Table(
    "group_permission",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
    Column("assigned_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    UniqueConstraint("group_id", "permission_id", name="unique_group_permission"),
)

# User-Permission direct relationship (for fine-grained control)
user_permission = Table(
    "user_permission",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
    Column("assigned_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    UniqueConstraint("user_id", "permission_id", name="unique_user_permission"),
)

# Sessions table for persistent session storage
sessions = Table(
    "sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(64), nullable=False, unique=True, index=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    Column("expires_at", DateTime, nullable=False),
    Column("last_activity", DateTime, nullable=False, default=datetime.now(tz=UTC)),
    Column("ip_address", String(45), nullable=True),  # IPv6 addresses can be up to 45 chars
)

# Export all tables for easy access
__all__ = [
    "metadata",
    "users",
    "groups",
    "permissions",
    "user_group",
    "group_permission",
    "user_permission",
    "sessions"
]
