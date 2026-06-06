"""Project-wide exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all application errors."""


class ValidationError(AppError):
    """Raised when input data fails validation."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ConflictError(AppError):
    """Raised when an operation conflicts with current state."""


class DatabaseError(AppError):
    """Raised when a database operation fails."""
