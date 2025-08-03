"""
CRUD Routes Generation for Fast-Admin

This module automatically generates CRUD routes for registered models,
supporting both async and sync operations.
"""

from typing import Any, Type

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, insert, select, Table, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.operators import eq

from .admin import BaseAdmin
from .forms import FormGenerator
from .static import static_handler


class CRUDRouter:
    """Generates CRUD routes for a registered table"""

    def __init__(
        self,
        table: Table,
        admin_class: Type[BaseAdmin],
        engine: Engine | AsyncEngine,
        templates: Jinja2Templates,
        model_name: str
    ):
        self.table = table
        self.admin_class = admin_class
        self.engine = engine
        self.templates = templates
        self.model_name = model_name
        self.is_async = isinstance(engine, AsyncEngine)
        self.form_generator = FormGenerator()

        # Get admin configuration
        self.admin_instance = admin_class(table)
        self.list_display = self.admin_instance.list_display or self._get_default_list_display()
        self.list_filter = self.admin_instance.list_filter
        self.search_fields = self.admin_instance.search_fields
        self.list_per_page = self.admin_instance.list_per_page

        # Generate Pydantic models for validation
        self.create_model = self.form_generator.generate_pydantic_model(
            self.table, f"{model_name.title()}Create"
        )
        self.update_model = self.form_generator.generate_pydantic_model(
            self.table, f"{model_name.title()}Update", for_update=True
        )

    def _get_default_list_display(self) -> list[str]:
        """Get default columns to display in list view"""
        columns = []
        for column in self.table.columns:
            # Skip large text fields and passwords by default
            if column.name not in ['password', 'password_hash'] and \
                not str(column.type).startswith('TEXT'):
                columns.append(column.name)
                if len(columns) >= 5:  # Limit to 5 columns
                    break
        return columns

    def _check_permissions(self, request: Request, action: str = "view"):
        """Check if user has permission for the given action"""
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Superusers have access to everything
        if user.get('is_superuser', False):
            return True

        # Staff users have access to admin functions
        if not user.get('is_staff', False):
            raise HTTPException(status_code=403, detail="Staff privileges required")

        # For now, all staff users can perform all actions
        # In a full implementation, you would check specific model permissions here
        return True

    def _get_template_context(self, request: Request, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get complete template context including static files"""
        context = {
            'request': request,
            'current_user': getattr(request.state, 'user', None),
            **static_handler.get_template_context()
        }
        if extra_context:
            context.update(extra_context)
        return context

    def get_router(self) -> APIRouter:
        """Create and return FastAPI router with CRUD routes"""
        router = APIRouter()

        # List view
        router.add_api_route(
            f"/{self.model_name}/",
            self.list_view,
            methods=["GET"],
            response_class=HTMLResponse
        )

        # Create view (GET form)
        router.add_api_route(
            f"/{self.model_name}/add/",
            self.create_view,
            methods=["GET"],
            response_class=HTMLResponse
        )

        # Create action (POST)
        router.add_api_route(
            f"/{self.model_name}/",
            self.create_action,
            methods=["POST"],
            response_model=None
        )

        # Detail view
        router.add_api_route(
            f"/{self.model_name}/{{item_id}}/",
            self.detail_view,
            methods=["GET"],
            response_class=HTMLResponse
        )

        # Edit view (GET form)
        router.add_api_route(
            f"/{self.model_name}/{{item_id}}/edit/",
            self.edit_view,
            methods=["GET"],
            response_class=HTMLResponse
        )

        # Update action (PUT)
        router.add_api_route(
            f"/{self.model_name}/{{item_id}}/",
            self.update_action,
            methods=["PUT"],
            response_model=None
        )

        # Delete action
        router.add_api_route(
            f"/{self.model_name}/{{item_id}}/",
            self.delete_action,
            methods=["DELETE"],
            response_model=None
        )

        # Bulk delete
        router.add_api_route(
            f"/{self.model_name}/bulk-delete/",
            self.bulk_delete_action,
            methods=["POST"],
            response_model=None
        )

        return router

    async def list_view(self, request: Request) -> HTMLResponse:
        """Display list of items with pagination, search, and filters"""
        self._check_permissions(request, "view")

        try:
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            search = request.query_params.get('search', '')
            order_by = request.query_params.get('order_by', self.list_display[0])
            reverse = request.query_params.get('reverse') == 'true'

            # Build base query
            query = select(self.table)
            count_query = select(func.count()).select_from(self.table)

            # Apply search
            if search and self.search_fields:
                search_conditions = []
                for field in self.search_fields:
                    if field in [col.name for col in self.table.columns]:
                        column = getattr(self.table.c, field)
                        search_conditions.append(column.ilike(f'%{search}%'))

                if search_conditions:
                    from sqlalchemy import or_
                    search_filter = or_(*search_conditions)
                    query = query.where(search_filter)
                    count_query = count_query.where(search_filter)

            # Apply filters
            for key, value in request.query_params.items():
                if key.startswith('filter_') and value:
                    field_name = key[7:]  # Remove 'filter_' prefix
                    if field_name in [col.name for col in self.table.columns]:
                        column = getattr(self.table.c, field_name)
                        query = query.where(eq(column, value))
                        count_query = count_query.where(eq(column, value))

            # Apply ordering
            if order_by in [col.name for col in self.table.columns]:
                column = getattr(self.table.c, order_by)
                if reverse:
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())

            # Get total count
            if self.is_async:
                async with self.engine.begin() as conn:
                    total_result = await conn.execute(count_query)
                    total = total_result.scalar()
            else:
                with self.engine.begin() as conn:
                    total_result = conn.execute(count_query)
                    total = total_result.scalar()

            # Apply pagination
            offset = (page - 1) * self.list_per_page
            query = query.offset(offset).limit(self.list_per_page)

            # Execute query
            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(query)
                    items = [dict(row._mapping) for row in result]
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(query)
                    items = [dict(row._mapping) for row in result]

            # Calculate pagination
            total_pages = (total + self.list_per_page - 1) // self.list_per_page
            pagination = {
                'current_page': page,
                'total_pages': total_pages,
                'total': total,
                'start': offset + 1,
                'end': min(offset + self.list_per_page, total),
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'previous_page': page - 1 if page > 1 else None,
                'next_page': page + 1 if page < total_pages else None,
                'pages': list(range(max(1, page - 2), min(total_pages + 1, page + 3)))
            }

            context = self._get_template_context(request, {
                'model_name': self.model_name,
                'items': items,
                'list_display': self.list_display,
                'search_fields': self.search_fields,
                'list_filter': self.list_filter,
                'pagination': pagination,
                'order_by': order_by,
                'reverse': reverse,
            })

            return self.templates.TemplateResponse('admin/list.html', context)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def create_view(self, request: Request) -> HTMLResponse:
        """Display create form"""
        self._check_permissions(request, "add")

        form_fields = self.form_generator.generate_form_fields(self.table)

        context = self._get_template_context(request, {
            'model_name': self.model_name,
            'form_fields': form_fields,
            'item': None,
        })

        return self.templates.TemplateResponse('admin/form.html', context)

    async def create_action(self, request: Request):
        """Handle create form submission"""
        self._check_permissions(request, "add")

        try:
            # Get form data
            form_data = await request.form()
            data = dict(form_data)

            # Handle action buttons
            action = data.pop('action', 'save')

            # Validate data
            validated_data = self.create_model(**data)

            # Insert into database
            insert_query = insert(self.table).values(**validated_data.dict())

            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(insert_query)
                    new_id = result.inserted_primary_key[0]
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(insert_query)
                    new_id = result.inserted_primary_key[0]

            # Handle different actions
            if action == 'save_and_add_another':
                return RedirectResponse(
                    url=f'/admin/{self.model_name}/add/',
                    status_code=302
                )
            elif action == 'save_and_continue':
                return RedirectResponse(
                    url=f'/admin/{self.model_name}/{new_id}/edit/',
                    status_code=302
                )
            else:  # save
                return RedirectResponse(
                    url=f'/admin/{self.model_name}/',
                    status_code=302
                )

        except Exception as e:
            # Return form with errors
            form_fields = self.form_generator.generate_form_fields(self.table)

            context = self._get_template_context(request, {
                'model_name': self.model_name,
                'form_fields': form_fields,
                'item': None,
                'errors': {'form': str(e)},
            })

            return self.templates.TemplateResponse('admin/form.html', context)

    async def detail_view(self, request: Request, item_id: int) -> HTMLResponse:
        """Display item details"""
        self._check_permissions(request, "view")

        try:
            # Get item
            query = select(self.table).where(eq(self.table.c.id, item_id))

            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(query)
                    item = result.mappings().first()
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(query)
                    item = result.mappings().first()

            if not item:
                raise HTTPException(status_code=404, detail="Item not found")

            # Get fields to display in detail view
            detail_fields = [col.name for col in self.table.columns if col.name not in ['password', 'password_hash']]

            context = self._get_template_context(request, {
                'model_name': self.model_name,
                'item': item,
                'detail_fields': detail_fields,
            })

            return self.templates.TemplateResponse('admin/detail.html', context)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def edit_view(self, request: Request, item_id: int) -> HTMLResponse:
        """Display edit form"""
        self._check_permissions(request, "change")

        try:
            # Get item
            query = select(self.table).where(eq(self.table.c.id, item_id))

            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(query)
                    item = result.mappings().first()
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(query)
                    item = result.mappings().first()

            if not item:
                raise HTTPException(status_code=404, detail="Item not found")

            form_fields = self.form_generator.generate_form_fields(self.table, for_update=True)

            context = self._get_template_context(request, {
                'model_name': self.model_name,
                'form_fields': form_fields,
                'item': item,
            })

            return self.templates.TemplateResponse('admin/form.html', context)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def update_action(self, request: Request, item_id: int):
        """Handle update form submission"""
        self._check_permissions(request, "change")

        try:
            # Get form data
            form_data = await request.form()
            data = dict(form_data)

            # Handle action buttons
            action = data.pop('action', 'save')

            # Validate data
            validated_data = self.update_model(**data)

            # Update in database
            update_query = update(self.table).where(
                eq(self.table.c.id, item_id)
            ).values(
                **validated_data.model_dump(exclude_unset=True)
            )

            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(update_query)
                    if result.rowcount == 0:
                        raise HTTPException(status_code=404, detail="Item not found")
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(update_query)
                    if result.rowcount == 0:
                        raise HTTPException(status_code=404, detail="Item not found")

            # Handle different actions
            if action == 'save_and_continue':
                return RedirectResponse(
                    url=f'/admin/{self.model_name}/{item_id}/edit/',
                    status_code=302
                )
            else:  # save
                return RedirectResponse(
                    url=f'/admin/{self.model_name}/',
                    status_code=302
                )

        except HTTPException:
            raise
        except Exception as e:
            # Return form with errors
            form_fields = self.form_generator.generate_form_fields(self.table, for_update=True)

            # Get current item for form
            query = select(self.table).where(eq(self.table.c.id, item_id))
            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(query)
                    row = result.mappings().first()
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(query)
                    row = result.mappings().first()

            item = row if row else None

            context = self._get_template_context(request, {
                'model_name': self.model_name,
                'form_fields': form_fields,
                'item': item,
                'errors': {'form': str(e)},
            })

            return self.templates.TemplateResponse('admin/form.html', context)

    async def delete_action(self, request: Request, item_id: int):
        """Handle delete action"""
        self._check_permissions(request, "delete")

        try:
            delete_query = delete(self.table).where(eq(self.table.c.id, item_id))

            if self.is_async:
                async with self.engine.begin() as conn:
                    result = await conn.execute(delete_query)
                    if result.rowcount == 0:
                        raise HTTPException(status_code=404, detail="Item not found")
            else:
                with self.engine.begin() as conn:
                    result = conn.execute(delete_query)
                    if result.rowcount == 0:
                        raise HTTPException(status_code=404, detail="Item not found")

            # Return success response for HTMX
            return Response(status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def bulk_delete_action(self, request: Request):
        """Handle bulk delete action"""
        self._check_permissions(request, "delete")

        try:
            form_data = await request.form()
            selected_items = form_data.getlist('selected-items')

            if not selected_items:
                raise HTTPException(status_code=400, detail="No items selected")

            # Convert to integers
            item_ids = [int(item_id) for item_id in selected_items]

            delete_query = delete(self.table).where(self.table.c.id.in_(item_ids))

            if self.is_async:
                async with self.engine.begin() as conn:
                    await conn.execute(delete_query)
            else:
                with self.engine.begin() as conn:
                    conn.execute(delete_query)

            # Redirect back to list view
            return RedirectResponse(
                url=f'/admin/{self.model_name}/',
                status_code=302
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


class RouteGenerator:
    """Main class for generating all admin routes"""

    def __init__(self, engine: Engine | AsyncEngine, templates: Jinja2Templates):
        self.engine = engine
        self.templates = templates
        self.registered_models: dict[str, dict[str, Any]] = {}

    def _get_template_context(self, request: Request, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get complete template context including static files"""
        context = {
            'request': request,
            'current_user': getattr(request.state, 'user', None),
            **static_handler.get_template_context()
        }
        if extra_context:
            context.update(extra_context)
        return context

    def register_model(self, table: Table, admin_class: Type[BaseAdmin], model_name: str):
        """Register a model for CRUD route generation"""
        self.registered_models[model_name] = {
            'table': table,
            'admin_class': admin_class,
            'model_name': model_name
        }

    def get_admin_router(self) -> APIRouter:
        """Generate complete admin router with all registered models"""
        main_router = APIRouter(prefix="/admin")

        # Admin dashboard/index route
        @main_router.get("/", response_class=HTMLResponse)
        async def admin_index(request: Request):
            context = self._get_template_context(request, {
                'registered_models': list(self.registered_models.keys()),
            })
            return self.templates.TemplateResponse('admin/index.html', context)

        # Add CRUD routes for each registered model
        for model_name, model_info in self.registered_models.items():
            crud_router = CRUDRouter(
                table=model_info['table'],
                admin_class=model_info['admin_class'],
                engine=self.engine,
                templates=self.templates,
                model_name=model_name
            )

            model_router = crud_router.get_router()
            main_router.include_router(model_router, tags=[model_name])

        return main_router
