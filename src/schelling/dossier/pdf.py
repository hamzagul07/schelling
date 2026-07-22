"""HTML -> PDF for the dossier (Session 26, D26.5).

Uses WeasyPrint, which honours the dossier's ``@page`` rules (page numbers, running header) and
renders inline SVG. Lazy-imported so the dependency is optional and CI is unaffected; a missing
install produces a friendly error rather than a traceback.
"""

from __future__ import annotations

from pathlib import Path


def weasyprint_available() -> bool:
    """True when WeasyPrint can be imported (the optional ``pdf`` toolchain is installed)."""
    try:
        import weasyprint  # type: ignore[import-not-found]  # noqa: F401
    except Exception:  # pragma: no cover - import guard; ImportError or a missing system lib
        return False
    return True


def html_to_pdf(html: str, out_path: Path) -> None:
    """Render ``html`` to a PDF at ``out_path``. Raises a friendly error if WeasyPrint is absent."""
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "PDF output needs WeasyPrint and its system libraries (pango, cairo): "
            "`pip install weasyprint`, or emit HTML without --pdf."
        ) from exc
    HTML(string=html).write_pdf(str(out_path))
