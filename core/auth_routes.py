"""
Authentication routes for Fast-Admin login/logout functionality
"""

import urllib.parse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth import AuthConfig, AuthManager
from .static import StaticFileHandler


def create_auth_router(auth_manager: AuthManager, templates: Jinja2Templates) -> APIRouter:
    """Create authentication router with login/logout routes"""

    router = APIRouter()

    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: str = None):
        """Display login page"""
        # If user is already authenticated, redirect to admin
        session_id = request.cookies.get(AuthConfig.SESSION_COOKIE_NAME)
        if session_id:
            session_data = auth_manager.session_manager.get_session(session_id)
            if session_data:
                return RedirectResponse(url="/admin/", status_code=302)

        # Get static files context
        static_handler = StaticFileHandler()
        context = static_handler.get_template_context()
        context.update({
            'request': request,
            'error': error,
        })

        return templates.TemplateResponse('auth/login.html', context)

    @router.post("/login")
    async def login_action(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        remember_me: bool = Form(False)
    ):
        """Handle login form submission"""
        try:
            # Authenticate user
            user = await auth_manager.authenticate_user(username, password)

            if not user:
                # Redirect back to login with error
                error_message = urllib.parse.quote("Invalid username or password")
                return RedirectResponse(
                    url=f"/admin/login?error={error_message}",
                    status_code=302
                )

            # Check if user has staff privileges
            if not user.get('is_staff', False):
                error_message = urllib.parse.quote("You do not have permission to access the admin panel")
                return RedirectResponse(
                    url=f"/admin/login?error={error_message}",
                    status_code=302
                )

            # Create session
            client_ip = request.client.host if request.client else None
            session_id = await auth_manager.session_manager.create_session(
                user['id'],
                ip_address=client_ip
            )

            # Create response and set session cookie
            response = RedirectResponse(url="/admin/", status_code=302)

            # Set session cookie
            max_age = AuthConfig.SESSION_EXPIRE_DAYS * 24 * 60 * 60 if remember_me else None
            response.set_cookie(
                key=AuthConfig.SESSION_COOKIE_NAME,
                value=session_id,
                max_age=max_age,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax"
            )

            return response

        except Exception as e:
            # Provide more detailed error information for debugging
            error_detail = str(e)
            print(f"Login error: {error_detail}")  # Log the error for server-side debugging
            error_message = urllib.parse.quote(f"An error occurred during login: {error_detail}")
            return RedirectResponse(
                url=f"/admin/login?error={error_message}",
                status_code=302
            )

    @router.get("/logout")
    @router.post("/logout")
    async def logout_action(request: Request):
        """Handle logout"""
        # Get session ID and destroy session
        session_id = request.cookies.get(AuthConfig.SESSION_COOKIE_NAME)
        if session_id:
            auth_manager.session_manager.destroy_session(session_id)

        # Create response and clear session cookie
        success_message = urllib.parse.quote("You have been logged out")
        response = RedirectResponse(url=f"/admin/login?success={success_message}", status_code=302)
        response.delete_cookie(
            key=AuthConfig.SESSION_COOKIE_NAME,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax"
        )

        return response

    return router
