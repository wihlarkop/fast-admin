"""
Fast-Admin base classes and admin site implementation.

This module provides the core Admin functionality similar to Django's admin system.
"""

from typing import Type

from fastapi import FastAPI
from sqlalchemy import Engine, Table
from sqlalchemy.ext.asyncio import AsyncEngine


class BaseAdmin:
    """
    Base admin class for customizing table administration.
    
    Similar to Django's ModelAdmin, this class allows customization
    of how tables are displayed and managed in the admin interface.
    """

    def __init__(self, table: Table | None = None):
        self.table = table
        self.table_name = table.name if table is not None else None

    # Display customization
    list_display: list[str] = []  # Columns to show in list view
    list_filter: list[str] = []  # Fields to filter by
    search_fields: list[str] = []  # Fields to search in
    ordering: list[str] = []  # Default ordering

    # Form customization  
    fields: list[str] | None = None  # Fields to show in forms
    exclude: list[str] = []  # Fields to exclude from forms
    readonly_fields: list[str] = []  # Read-only fields

    # Pagination
    list_per_page: int = 25

    def get_list_display(self) -> list[str]:
        """Get list of fields to display in list view."""
        if self.list_display:
            return self.list_display
        # Default: show all columns except password fields
        if self.table is not None:
            return [
                col.name for col in self.table.columns
                if 'password' not in col.name.lower()
            ]
        return []

    def get_fields(self) -> list[str]:
        """Get list of fields to show in forms."""
        if self.fields is not None:
            return self.fields
        # Default: all columns except auto-generated ones
        if self.table is not None:
            excluded = {'id', 'created_at', 'updated_at'} | set(self.exclude)
            return [
                col.name for col in self.table.columns
                if col.name not in excluded
            ]
        return []

    def get_readonly_fields(self) -> list[str]:
        """Get list of read-only fields."""
        return self.readonly_fields

    def get_ordering(self) -> list[str]:
        """Get default ordering for list view."""
        if self.ordering:
            return self.ordering
        # Default: order by primary key
        if self.table is not None:
            pk_cols = [col.name for col in self.table.primary_key.columns]
            return pk_cols if pk_cols else ['id']
        return ['id']


class FastAdmin:
    """
    Main admin site class for registering and managing table administration.
    
    Similar to Django's admin.site, this class manages the registration
    of tables and their corresponding admin classes.
    """

    def __init__(self, app: FastAPI | None = None, engine: Engine | AsyncEngine | None = None):
        self.app = app
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine) if engine else False

        # Registry of registered tables and their admin classes
        self._registry: dict[str, BaseAdmin] = {}

        # Built-in admin instances for auth tables
        self._auth_admins: dict[str, BaseAdmin] = {}

        if app and engine:
            self.init_app(app, engine)

    def init_app(self, app: FastAPI, engine: Engine | AsyncEngine) -> None:
        """Initialize FastAdmin with FastAPI app and database engine."""
        self.app = app
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)

        # Register built-in auth tables
        self._register_auth_tables()

        # Add admin routes to FastAPI app
        self._setup_routes()

    def register(
        self,
        table: Table,
        admin_class: Type[BaseAdmin] | None = None
    ) -> None:
        """
        Register a table with optional custom admin class.
        
        Args:
            table: SQLAlchemy Table to register
            admin_class: Optional custom admin class (defaults to BaseAdmin)
        """
        if admin_class is None:
            admin_class = BaseAdmin

        admin_instance = admin_class(table)
        self._registry[table.name] = admin_instance

    def unregister(self, table: Table | str) -> None:
        """Unregister a table from admin."""
        table_name = table.name if isinstance(table, Table) else table
        self._registry.pop(table_name, None)

    def get_admin(self, table_name: str) -> BaseAdmin | None:
        """Get admin instance for a table."""
        return self._registry.get(table_name)

    def get_registered_tables(self) -> list[str]:
        """Get list of all registered table names."""
        return list(self._registry.keys())

    def _register_auth_tables(self) -> None:
        """Register built-in authentication tables."""
        from .models import users, groups, permissions, user_group, group_permission, user_permission

        # Custom admin for users table
        class UserAdmin(BaseAdmin):
            def __init__(self, table: Table):
                super().__init__(table)
                self.list_display = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']
                self.list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
                self.search_fields = ['username', 'email', 'first_name', 'last_name']
                self.exclude = ['password_hash']
                self.readonly_fields = ['date_joined', 'last_login']

        # Custom admin for groups table  
        class GroupAdmin(BaseAdmin):
            def __init__(self, table: Table):
                super().__init__(table)
                self.list_display = ['id', 'name', 'description', 'created_at']
                self.search_fields = ['name', 'description']

        # Custom admin for permissions table
        class PermissionAdmin(BaseAdmin):
            def __init__(self, table: Table):
                super().__init__(table)
                self.list_display = ['id', 'name', 'codename', 'content_type', 'created_at']
                self.list_filter = ['content_type', 'created_at']
                self.search_fields = ['name', 'codename', 'content_type']

        # Register auth tables with custom admin classes
        self.register(users, UserAdmin)
        self.register(groups, GroupAdmin)
        self.register(permissions, PermissionAdmin)
        self.register(user_group)
        self.register(group_permission)
        self.register(user_permission)

    def _setup_routes(self) -> None:
        """Setup admin routes in FastAPI app."""
        if not self.app:
            return

        from .routes import RouteGenerator
        from .static import StaticFileHandler
        from .auth import AuthManager, AdminAuthMiddleware
        from .auth_routes import create_auth_router

        # Setup static files FIRST (before any routes)
        static_handler = StaticFileHandler()
        static_handler.setup_static_files(self.app)

        # Setup templates
        templates = static_handler.get_templates()

        # Setup authentication
        auth_manager = AuthManager(self.engine)
        auth_middleware = AdminAuthMiddleware(auth_manager)

        # Add authentication middleware
        self.app.middleware("http")(auth_middleware)

        # Create route generator
        route_generator = RouteGenerator(self.engine, templates)

        # Register all admin models with route generator
        for table_name, admin_instance in self._registry.items():
            route_generator.register_model(
                table=admin_instance.table,
                admin_class=type(admin_instance),
                model_name=table_name
            )

        # Add admin router to app
        admin_router = route_generator.get_admin_router()
        self.app.include_router(admin_router)

        # Create authentication routes LAST
        auth_router = create_auth_router(auth_manager, templates)
        self.app.include_router(auth_router, prefix="/admin", tags=["auth"])


# Global admin instance
admin = FastAdmin()