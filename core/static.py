"""
Static file handling for Fast-Admin.

This module provides utilities for serving static assets (CSS, JS, images)
and integrating them with FastAPI applications.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


class StaticFileHandler:
    """Handles static file serving for Fast-Admin."""

    def __init__(self):
        self.static_dir = Path(__file__).parent / "static"
        self.css_dir = self.static_dir / "css"
        self.js_dir = self.static_dir / "js"
        self.images_dir = self.static_dir / "images"
        self.templates_dir = Path(__file__).parent / "templates"

    def setup_static_files(self, app: FastAPI, mount_path: str = "/admin/static") -> None:
        """
        Mount static files to FastAPI application.
        
        Args:
            app: FastAPI application instance
            mount_path: URL path to mount static files at
        """
        if self.static_dir.exists():
            app.mount(
                mount_path,
                StaticFiles(directory=str(self.static_dir)),
                name="admin_static"
            )

    def get_css_files(self) -> list[str]:
        """Get list of CSS files to include in templates."""
        css_files = []

        # TailwindCSS v4 uses JavaScript, not CSS files
        # Only include admin.css for any custom styles
        admin_css_file = self.css_dir / "admin.css"
        if admin_css_file.exists():
            css_files.append("/admin/static/css/admin.css")

        return css_files

    def get_js_files(self) -> list[str]:
        """Get list of JavaScript files to include in templates."""
        js_files = []

        # HTMX (required)
        htmx_file = self.js_dir / "htmx.min.js"
        if htmx_file.exists():
            js_files.append("/admin/static/js/htmx.min.js")

        # Fast-Admin JavaScript Modules (load in correct order)
        modules_dir = self.js_dir / "modules"
        if modules_dir.exists():
            # Table Manager
            table_manager_file = modules_dir / "table-manager.js"
            if table_manager_file.exists():
                js_files.append("/admin/static/js/modules/table-manager.js")
            
            # Bulk Actions
            bulk_actions_file = modules_dir / "bulk-actions.js"
            if bulk_actions_file.exists():
                js_files.append("/admin/static/js/modules/bulk-actions.js")
            
            # Pagination Manager
            pagination_file = modules_dir / "pagination.js"
            if pagination_file.exists():
                js_files.append("/admin/static/js/modules/pagination.js")

        # Main Admin JS (load last as it coordinates all modules)
        admin_js_file = self.js_dir / "admin.js"
        if admin_js_file.exists():
            js_files.append("/admin/static/js/admin.js")

        return js_files

    def get_templates(self) -> Jinja2Templates:
        """
        Get Jinja2Templates instance for rendering admin templates.
        
        Returns:
            Configured Jinja2Templates instance
        """
        return Jinja2Templates(directory=str(self.templates_dir))

    def get_template_context(self) -> dict:
        """
        Get template context with static asset URLs.
        
        Returns:
            Dictionary with CSS and JS file lists for templates
        """
        return {
            "css_files": self.get_css_files(),
            "js_files": self.get_js_files(),
            "static_url": "/admin/static"
        }

    def get_asset_context(self) -> dict:
        """
        Get template context with static asset URLs.
        
        Returns:
            Dictionary with CSS and JS file lists for templates
        """
        return self.get_template_context()


# Global static file handler instance
static_handler = StaticFileHandler()
