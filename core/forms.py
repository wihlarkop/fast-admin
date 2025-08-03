"""
Auto-form generation from SQLAlchemy table metadata.

This module provides functionality to automatically generate:
- Pydantic models from SQLAlchemy tables
- HTML form fields with appropriate input types
- Validation logic based on column constraints
"""

from datetime import datetime
from enum import Enum
from typing import Any, Type, Dict, List, Tuple

from pydantic import BaseModel, create_model, Field
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, select


class FormFieldType(str, Enum):
    """HTML form field types mapping."""
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    SELECT = "select"
    DATE = "date"
    DATETIME = "datetime-local"
    HIDDEN = "hidden"


class FormField:
    """Represents a form field with HTML attributes and validation."""

    def __init__(
        self,
        name: str,
        field_type: FormFieldType,
        label: str | None = None,
        required: bool = False,
        placeholder: str | None = None,
        help_text: str | None = None,
        max_length: int | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        readonly: bool = False,
        choices: list[tuple] | None = None,
        default: Any = None,
    ):
        self.name = name
        self.field_type = field_type
        self.label = label or name.replace('_', ' ').title()
        self.required = required
        self.placeholder = placeholder
        self.help_text = help_text
        self.max_length = max_length
        self.min_value = min_value
        self.max_value = max_value
        self.readonly = readonly
        self.choices = choices or []
        self.default = default

    def to_dict(self) -> dict[str, Any]:
        """Convert form field to dictionary for template rendering."""
        return {
            'name': self.name,
            'type': self.field_type.value,
            'label': self.label,
            'required': self.required,
            'placeholder': self.placeholder,
            'help_text': self.help_text,
            'max_length': self.max_length,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'readonly': self.readonly,
            'choices': self.choices,
            'default': self.default,
        }


class FormGenerator:
    """Generates forms and Pydantic models from SQLAlchemy tables."""

    def __init__(self):
        self.type_mapping = {
            Integer: (int, FormFieldType.NUMBER),
            String: (str, FormFieldType.TEXT),
            Text: (str, FormFieldType.TEXTAREA),
            Boolean: (bool, FormFieldType.CHECKBOX),
            DateTime: (datetime, FormFieldType.DATETIME),
            Float: (float, FormFieldType.NUMBER),
        }
        self.engine = None
        
    def set_engine(self, engine):
        """Set the database engine for fetching related data."""
        self.engine = engine
        print(f"DEBUG: Engine set in FormGenerator: {engine}")
        
    def get_related_choices(self, foreign_key) -> list[tuple[Any, str]]:
        """
        Fetch related data for a foreign key to populate dropdown choices.
        
        Returns a list of tuples (id, display_value) for the dropdown.
        """
        print(f"DEBUG: get_related_choices called for {foreign_key}")
        
        if not self.engine:
            print("DEBUG: No engine set, returning empty choices")
            return []
            
        # Get the target table and column
        target_table_name = foreign_key.target_fullname.split('.')[0]
        print(f"DEBUG: Target table name: {target_table_name}")
        
        # Check if target table exists in metadata
        if target_table_name not in foreign_key.column.table.metadata.tables:
            print(f"DEBUG: Target table {target_table_name} not found in metadata")
            return []
            
        target_table = foreign_key.column.table.metadata.tables[target_table_name]
        print(f"DEBUG: Target table columns: {[c.name for c in target_table.columns]}")
        
        # Build a query to get id and a display field
        # Try to find a good display field (name, title, etc.)
        display_fields = ['name', 'title', 'label', 'username', 'email', 'description']
        display_field = None
        
        for field in display_fields:
            if field in target_table.columns:
                display_field = field
                print(f"DEBUG: Found display field: {field}")
                break
                
        # If no good display field found, use the primary key
        if not display_field:
            primary_key_cols = list(target_table.primary_key.columns)
            if primary_key_cols:
                display_field = primary_key_cols[0].name
                print(f"DEBUG: Using primary key as display field: {display_field}")
            else:
                print("DEBUG: No primary key found, using first column")
                display_field = list(target_table.columns)[0].name
            
        # Build and execute the query
        primary_key_col = list(target_table.primary_key.columns)[0] if target_table.primary_key.columns else list(target_table.columns)[0]
        
        query = select(
            target_table.c[primary_key_col.name],
            target_table.c[display_field]
        ).order_by(target_table.c[display_field])
        print(f"DEBUG: Query: {query}")
        
        try:
            # Check if engine is async
            from sqlalchemy.ext.asyncio import AsyncEngine
            is_async = isinstance(self.engine, AsyncEngine)
            
            if is_async:
                # For async engines, we need to use a sync_engine from pool
                # This is a workaround since form generation happens in sync context
                sync_engine = self.engine.sync_engine if hasattr(self.engine, 'sync_engine') else self.engine
                with sync_engine.connect() as conn:
                    result = conn.execute(query)
                    choices = [(row[0], str(row[1])) for row in result]
                    print(f"DEBUG: Retrieved {len(choices)} choices")
                    return choices
            else:
                # For synchronous engines
                with self.engine.connect() as conn:
                    result = conn.execute(query)
                    choices = [(row[0], str(row[1])) for row in result]
                    print(f"DEBUG: Retrieved {len(choices)} choices")
                    return choices
        except Exception as e:
            print(f"ERROR: Failed to fetch related choices: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_python_type_and_field_type(self, column: Column) -> tuple[Type, FormFieldType]:
        """Map SQLAlchemy column type to Python type and HTML field type."""
        sql_type = type(column.type)

        # Special cases based on column name
        if 'email' in column.name.lower():
            return str, FormFieldType.EMAIL
        elif 'password' in column.name.lower():
            return str, FormFieldType.PASSWORD
        elif column.name.lower() in ['description', 'content', 'notes']:
            return str, FormFieldType.TEXTAREA

        # Map based on SQL type
        for sql_type_class, (python_type, field_type) in self.type_mapping.items():
            if isinstance(column.type, sql_type_class):
                return python_type, field_type

        # Default fallback
        return str, FormFieldType.TEXT

    def create_form_field(self, column: Column) -> FormField:
        """Create a FormField from SQLAlchemy column."""
        python_type, field_type = self.get_python_type_and_field_type(column)
        
        # Check if column is a foreign key
        choices = []
        if column.foreign_keys:
            print(f"DEBUG: Foreign key detected for column {column.name}")
            field_type = FormFieldType.SELECT
            
            # Get the first foreign key (usually there's only one)
            foreign_key = next(iter(column.foreign_keys))
            print(f"DEBUG: Foreign key target: {foreign_key.target_fullname}")
            
            # Get choices for the dropdown
            related_choices = self.get_related_choices(foreign_key)
            print(f"DEBUG: Retrieved {len(related_choices)} choices for {column.name}")
            
            # Add an empty option for nullable fields at the beginning
            if column.nullable:
                choices = [('', '-- Select --')] + related_choices
            else:
                choices = related_choices
            
        # Determine if field is required
        required = not column.nullable and column.default is None and not column.primary_key

        # Get max length for string fields
        max_length = None
        if hasattr(column.type, 'length') and column.type.length:
            max_length = column.type.length

        # Generate placeholder text
        placeholder = None
        if field_type in [FormFieldType.TEXT, FormFieldType.EMAIL]:
            placeholder = f"Enter {column.name.replace('_', ' ').lower()}"
        elif field_type == FormFieldType.TEXTAREA:
            placeholder = f"Enter {column.name.replace('_', ' ').lower()}..."
        elif field_type == FormFieldType.SELECT and not choices:
            placeholder = f"Select {column.name.replace('_', ' ').lower()}"

        # Determine if field should be readonly
        readonly = (
            column.primary_key or
            column.name in ['created_at', 'updated_at', 'date_joined', 'last_login']
        )

        # Set field as hidden for password fields in edit mode
        if 'password' in column.name.lower():
            field_type = FormFieldType.HIDDEN

        # Generate help text for foreign key fields
        help_text = None
        if column.foreign_keys:
            target_table = next(iter(column.foreign_keys)).target_fullname.split('.')[0]
            help_text = f"Select a related {target_table.replace('_', ' ')}"

        return FormField(
            name=column.name,
            field_type=field_type,
            required=required,
            placeholder=placeholder,
            help_text=help_text,
            max_length=max_length,
            readonly=readonly,
            choices=choices,
        )

    def generate_form_fields(
        self,
        table: Table,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        readonly_fields: list[str] | None = None,
        for_update: bool = False,
    ) -> list[FormField]:
        """Generate form fields from table columns."""
        exclude = exclude or []
        readonly_fields = readonly_fields or []

        # Auto-exclude certain fields
        auto_exclude = ['id'] if 'id' in [col.name for col in table.columns] else []
        
        # Exclude timestamp fields when adding new data (not for update)
        if not for_update:
            timestamp_fields = ['created_at', 'updated_at', 'date_joined', 'last_login', 'assigned_at']
            auto_exclude.extend([field for field in timestamp_fields 
                               if field in [col.name for col in table.columns]])
        
        exclude.extend(auto_exclude)

        fields = []
        for column in table.columns:
            # Skip excluded fields
            if column.name in exclude:
                continue

            # Include only specified fields if include list is provided
            if include and column.name not in include:
                continue

            field = self.create_form_field(column)

            # Mark as readonly if specified
            if column.name in readonly_fields:
                field.readonly = True

            fields.append(field)

        return fields

    def generate_pydantic_model(
        self,
        table: Table,
        model_name: str | None = None,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        for_update: bool = False,
    ) -> Type[BaseModel]:
        """Generate a Pydantic model from SQLAlchemy table."""
        model_name = model_name or f"{table.name.title()}Model"
        exclude = exclude or []

        # Auto-exclude certain fields based on operation type
        if for_update:
            # For updates, exclude timestamp fields but allow other fields
            auto_exclude = ['created_at', 'date_joined', 'assigned_at']
        else:
            # For creates, exclude ID and all timestamp fields
            auto_exclude = ['id', 'created_at', 'updated_at', 'date_joined', 'last_login', 'assigned_at']

        exclude.extend(auto_exclude)

        fields = {}
        for column in table.columns:
            # Skip excluded fields
            if column.name in exclude:
                continue

            # Include only specified fields if include list is provided
            if include and column.name not in include:
                continue

            python_type, _ = self.get_python_type_and_field_type(column)

            # Handle nullable fields
            if column.nullable:
                python_type = python_type | None
                default_value = None
            else:
                default_value = ...  # Required field

            # Add validation based on column constraints
            field_kwargs = {}
            if hasattr(column.type, 'length') and column.type.length:
                field_kwargs['max_length'] = column.type.length

            if field_kwargs:
                fields[column.name] = (python_type, Field(default=default_value, **field_kwargs))
            else:
                fields[column.name] = (python_type, default_value)

        return create_model(model_name, **fields)

    def generate_update_model(
        self,
        table: Table,
        model_name: str | None = None,
    ) -> Type[BaseModel]:
        """Generate a Pydantic model for update operations (all fields optional)."""
        model_name = model_name or f"{table.name.title()}UpdateModel"

        # Exclude auto-managed fields
        exclude = ['id', 'created_at', 'updated_at', 'date_joined', 'assigned_at']

        fields = {}
        for column in table.columns:
            if column.name in exclude:
                continue

            python_type, _ = self.get_python_type_and_field_type(column)

            # Make all fields optional for updates
            fields[column.name] = (python_type | None, None)

        return create_model(model_name, **fields)


# Global form generator instance
form_generator = FormGenerator()