"""
Auto-form generation from SQLAlchemy table metadata.

This module provides functionality to automatically generate:
- Pydantic models from SQLAlchemy tables
- HTML form fields with appropriate input types
- Validation logic based on column constraints
"""

from datetime import datetime
from enum import Enum
from typing import Any, Type

from pydantic import BaseModel, create_model, Field
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table, Text


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

        # Determine if field should be readonly
        readonly = (
            column.primary_key or
            column.name in ['created_at', 'updated_at', 'date_joined', 'last_login']
        )

        # Set field as hidden for password fields in edit mode
        if 'password' in column.name.lower():
            field_type = FormFieldType.HIDDEN

        return FormField(
            name=column.name,
            field_type=field_type,
            required=required,
            placeholder=placeholder,
            max_length=max_length,
            readonly=readonly,
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
            auto_exclude = ['created_at', 'date_joined']
        else:
            # For creates, exclude ID and all timestamp fields
            auto_exclude = ['id', 'created_at', 'updated_at', 'date_joined', 'last_login']

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
        exclude = ['id', 'created_at', 'updated_at', 'date_joined']

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