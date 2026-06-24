# src/bb_paxdata/infrastructure/templates_engine/engine.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import StrictUndefined, TemplateSyntaxError, meta
from jinja2.sandbox import SandboxedEnvironment, SecurityError


class TemplateSecurityError(Exception):
    """Raised when template contains unsafe operations."""

    pass


class SafeTemplateEngine:
    """Jinja2 sandboxed template engine for secure template rendering."""

    def __init__(self):
        self.env = SandboxedEnvironment(
            autoescape=True,
            undefined=StrictUndefined,
        )
        # Register safe custom filters
        self.env.filters["format_date"] = self._format_date
        self.env.filters["risk_badge"] = self._risk_badge
        self.env.filters["sbi_label"] = self._sbi_label
        self.env.filters["round2"] = lambda x: round(x, 2) if x is not None else 0
        self.env.filters["truncate"] = self._truncate

    def render(self, template_str: str, context: dict) -> str:
        """
        Render template with given context.

        Args:
            template_str: Jinja2 template string
            context: Template variables

        Returns:
            Rendered string

        Raises:
            TemplateSyntaxError: Syntax error in template
            TemplateSecurityError: Unsafe operation detected
        """
        try:
            template = self.env.from_string(template_str)
            return template.render(**context)
        except SecurityError as e:
            raise TemplateSecurityError(f"Unsafe operation detected: {e}")
        except Exception:
            raise

    def validate_syntax(self, template_str: str) -> list[dict]:
        """
        Validate template syntax.

        Returns:
            List of errors with line numbers and messages
        """
        errors = []
        try:
            self.env.parse(template_str)
        except TemplateSyntaxError as e:
            errors.append(
                {"line": e.lineno, "message": str(e.message), "type": "syntax_error"}
            )
        return errors

    def extract_variables(self, template_str: str) -> list[str]:
        """
        Extract variable names from template.

        Returns:
            List of variable names used in template
        """
        ast = self.env.parse(template_str)
        return list(meta.find_undeclared_variables(ast))

    def _format_date(self, value: Any, format_str: str = "%Y-%m-%d") -> str:
        """Format date value."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", ""))
            except ValueError:
                return value
        if isinstance(value, datetime):
            return value.strftime(format_str)
        return str(value)

    def _risk_badge(self, score: float) -> str:
        """Convert risk score to badge label."""
        if score is None:
            return "UNKNOWN"
        if score >= 7:
            return "HIGH"
        if score >= 4:
            return "MEDIUM"
        return "LOW"

    def _sbi_label(self, code: str) -> str:
        """Convert SBI code to label."""
        mapping = {"S": "Statement", "B": "Behavior", "I": "Intent"}
        return mapping.get(str(code).upper(), code)

    def _truncate(self, value: str, length: int = 100) -> str:
        """Truncate string to length."""
        if value is None:
            return ""
        if len(value) <= length:
            return value
        return value[:length] + "..."
