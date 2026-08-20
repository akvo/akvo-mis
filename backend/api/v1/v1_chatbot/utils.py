import re


def get_page_context(page_url: str) -> str:
    """
    Derive a human-readable page label from a URL path.
    No hardcoded map — new routes are covered automatically.

    Examples:
        '/control-center/form-builder/42/edit' -> 'Form Builder — Edit'
        '/control-center/master-data/administration' -> 'Master Data'
        '/control-center/approvals' -> 'Approvals'
        '/data' -> 'General Platform'
    """
    if not page_url or not isinstance(page_url, str):
        return "General Platform"

    # Strip query string, hash fragment, and trailing slash
    path = page_url.split("?")[0].split("#")[0].rstrip("/")

    # Drop known container prefix segments
    path = re.sub(r"^/(control-center|data)", "", path).lstrip("/")

    # Drop dynamic path parameter segments (pure integers or UUID strings)
    segments = [
        s
        for s in path.split("/")
        if s
        and not re.match(r"^\d+$", s)
        and not re.match(r"^[0-9a-f-]{36}$", s)
    ]

    # Titlecase each segment (kebab-case -> Title Words)
    label_parts = [s.replace("-", " ").title() for s in segments]

    return " — ".join(label_parts) if label_parts else "General Platform"
