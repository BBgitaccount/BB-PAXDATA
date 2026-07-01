# src/bb_paxdata/infrastructure/export/latex_utils.py
from __future__ import annotations

import re

import jinja2

# Define the custom Jinja2 Environment to avoid delimiter conflicts with LaTeX
latex_env = jinja2.Environment(  # nosec B701
    block_start_string="\\BLOCK{",
    block_end_string="}",
    variable_start_string="\\VAR{",
    variable_end_string="}",
    comment_start_string="\\#{",
    comment_end_string="}",
    line_statement_prefix="%%",
    line_comment_prefix="%#",
    trim_blocks=True,
    autoescape=False,
)


def escape_latex(text: str) -> str:
    """
    Safely escape LaTeX special characters in string inputs.
    Must escape backslashes first to prevent double-escaping.
    """
    if not isinstance(text, str):
        return str(text)

    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }

    # First, handle backslashes separately so we don't escape backslashes
    # introduced by other replacements
    parts = text.split("\\")
    regex = re.compile(r"([&%$#_{}~^])")

    escaped_parts = []
    for part in parts:
        escaped_part = regex.sub(lambda match: conv[match.group(1)], part)
        escaped_parts.append(escaped_part)

    return r"\textbackslash{}".join(escaped_parts)


# Register the LaTeX escaping filter
latex_env.filters["escape_latex"] = escape_latex


def render_latex_template(template_str: str, context: dict) -> str:
    """Render a LaTeX document from template string and context."""
    template = latex_env.from_string(template_str)
    return template.render(context)
