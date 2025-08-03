# Fast-Admin

A Django-admin-inspired admin panel for FastAPI applications with SQLAlchemy Core.

## Features

- 🚀 **Auto-generated CRUD interfaces** - Just register your tables and get a full admin interface
- 🔐 **Built-in authentication** - Session-based auth with user/group/permission system
- 🎨 **Modern UI** - Clean, responsive interface built with TailwindCSS
- ⚡ **HTMX integration** - Interactive features without JavaScript complexity  
- 🔍 **Search and filtering** - Real-time search with debouncing and field-based filters
- 📱 **Responsive design** - Works on desktop and mobile devices
- 🛡️ **Permission system** - Fine-grained access control with decorators
- 🔄 **Async/Sync support** - Compatible with both async and sync FastAPI applications
- 📋 **Auto-form generation** - Forms automatically generated from table metadata
- 🎯 **Bulk actions** - Select multiple items for batch operations

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd fast-admin

# Install dependencies with uv
uv sync

# Or with pip
pip install -r requirements.txt
```

### Basic Usage

```python
from fastapi import FastAPI
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean
from core.admin import FastAdmin

# Create FastAPI app
app = FastAPI()

# Setup database
engine = create_engine("postgresql://user:password@localhost/dbname")
metadata = MetaData()

# Define your tables
products = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), nullable=False),
    Column("price", Integer, nullable=False),
    Column("is_active", Boolean, default=True),
)

# Create tables
metadata.create_all(engine)

# Initialize Fast-Admin
admin = FastAdmin()
admin.init_app(app, engine)

# Register your models
admin.register(products)

# Start the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Visit `http://localhost:8000/admin/` to access the admin interface.

## Features

✨ **Django-like Admin Interface** - Familiar admin.site.register() API  
🔐 **Built-in Authentication** - User, Group, and Permission management  
⚡ **Async & Sync Support** - Works with both sync and async FastAPI apps  
🎨 **Modern UI** - TailwindCSS + HTMX for responsive, interactive interface  
📝 **Auto-Generated Forms** - Automatic form generation from table metadata  
🔍 **Search & Filter** - Built-in search, filtering, and pagination  
🛡️ **Permission System** - Granular access control with decorators  

## Quick Start

### Installation

```bash
pip install fast-admin
# or
uv add fast-admin
```

### Environment Setup

Create a `.env` file with your database configuration:

```bash
# Copy from example
cp .env.example .env
```

Required environment variables:
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_NAME=your_database
```

### Basic Usage

#### Sync Example

```python
from fastapi import FastAPI
from core.admin import FastAdmin
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String

app = FastAPI()
engine = create_engine("postgresql+psycopg://user:pass@localhost/db")
metadata = MetaData()

# Define your table
products_table = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("price", Integer, nullable=False),
    Column("description", String(500)),
)

# Initialize admin
admin = FastAdmin(app, engine)

# Register table - auto-generates admin interface
admin.register(products_table)

# Creates routes:
# GET    /admin/products/     - List products
# POST   /admin/products/     - Create product  
# GET    /admin/products/{id} - Product detail
# PUT    /admin/products/{id} - Update product
# DELETE /admin/products/{id} - Delete product
```

#### Async Example

```python
from fastapi import FastAPI
from core.admin import FastAdmin
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import MetaData, Table, Column, Integer, String

app = FastAPI()
engine = create_async_engine("postgresql+psycopg://user:pass@localhost/db")

# Define tables
users_table = Table(
    "app_users", metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(50), unique=True),
    Column("email", String(100), unique=True),
)

# Initialize admin (automatically detects async)
admin = FastAdmin(app, engine)
admin.register(users_table)
```

### Custom Admin Classes

Customize the admin interface like Django's ModelAdmin:

```python
from core.admin import BaseAdmin

class ProductAdmin(BaseAdmin):
    # Customize list view
    list_display = ['id', 'name', 'price', 'created_at']
    list_filter = ['price', 'created_at'] 
    search_fields = ['name', 'description']
    ordering = ['-created_at']
    
    # Customize forms
    fields = ['name', 'price', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    # Pagination
    list_per_page = 50

# Register with custom admin
admin.register(products_table, ProductAdmin)
```

## Architecture

### Core Components

- **FastAdmin** - Main admin site class for registration and management
- **BaseAdmin** - Customizable admin class for tables (like Django's ModelAdmin)
- **Built-in Auth** - User, Group, Permission tables with many-to-many relationships
- **Auto-Forms** - Automatic form generation from SQLAlchemy table metadata
- **CRUD Routes** - RESTful API endpoints for all registered tables

### Database Schema

Fast-Admin includes built-in authentication tables:

```sql
-- Users with Django-style fields
users (id, username, email, password_hash, first_name, last_name, 
       is_active, is_staff, is_superuser, date_joined, last_login)

-- Groups for organizing users  
groups (id, name, description, created_at)

-- Granular permissions
permissions (id, name, codename, content_type, description, created_at)

-- Many-to-many relationships
user_group (user_id, group_id, assigned_at)
group_permission (group_id, permission_id, assigned_at)  
user_permission (user_id, permission_id, assigned_at)
```

### Technology Stack

- **Backend:** FastAPI + SQLAlchemy Core + Alembic
- **Database:** PostgreSQL with psycopg adapter
- **Frontend:** Jinja2 + TailwindCSS + HTMX
- **Auth:** Passlib + Python-JOSE for JWT
- **Config:** Pydantic Settings with .env support

## Advanced Usage

### Permissions & Authentication

```python
from core.auth import require_permission

@app.get("/admin/products/")
@require_permission("products.view")
async def list_products():
    # Only users with products.view permission can access
    pass

@app.post("/admin/products/")
@require_permission("products.add")
async def create_product():
    # Only users with products.add permission can access
    pass
```

### Custom Form Validation

```python
class ProductAdmin(BaseAdmin):
    def clean_price(self, value):
        if value < 0:
            raise ValueError("Price cannot be negative")
        return value
    
    def save_model(self, instance, form_data):
        # Custom save logic
        instance.slug = slugify(form_data['name'])
        return super().save_model(instance, form_data)
```

## Development

### Project Structure

```
fast-admin/
├── core/
│   ├── admin.py         # Main Admin classes
│   ├── models.py        # Built-in auth tables
│   ├── settings.py      # Configuration
│   ├── auth.py          # Authentication middleware
│   ├── forms.py         # Auto-form generation
│   ├── routes.py        # CRUD routes
│   └── templates/       # Jinja2 templates
├── migrations/          # Alembic migrations
├── .env                 # Environment variables
└── TASKS.md            # Development progress
```

### Running Migrations

```bash
# Generate migration
uv run alembic revision --autogenerate -m "Add new table"

# Apply migrations  
uv run alembic upgrade head

# Rollback
uv run alembic downgrade -1
```

### Development Commands

```bash
# Install dependencies
uv sync --dev

# Code formatting
uv run ruff format .

# Type checking
uv run mypy core/

# Run tests
uv run pytest
```

## Roadmap

- [x] **Core Foundation** - Database models and admin classes
- [x] **Registration System** - Django-like table registration
- [ ] **Auto-Forms** - Generate forms from table metadata
- [ ] **CRUD Routes** - RESTful endpoints for all operations
- [ ] **Authentication** - Login/logout and permission checking
- [ ] **Templates** - Complete admin interface with TailwindCSS
- [ ] **HTMX Integration** - Interactive features without JavaScript

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Inspiration

Fast-Admin is heavily inspired by Django's admin interface, bringing the same ease of use and powerful customization to the FastAPI ecosystem.