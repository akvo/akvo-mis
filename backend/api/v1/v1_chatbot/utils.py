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
    path = page_url.split("?")[0].split("#")[0].strip()
    clean_path = path.strip("/")

    if not clean_path:
        return "General Platform"

    # Specific landing page contexts
    if clean_path == "data":
        return "Data Management"
    if clean_path == "control-center":
        return "Control Center"

    # Drop known container prefix segments for sub-routes
    sub_path = re.sub(r"^(control-center|data)/?", "", clean_path).strip("/")

    # Drop dynamic path parameter segments (pure integers or UUID strings)
    segments = [
        s
        for s in sub_path.split("/")
        if s
        and not re.match(r"^\d+$", s)
        and not re.match(r"^[0-9a-f-]{36}$", s)
    ]

    # Titlecase each segment (kebab-case -> Title Words)
    label_parts = [s.replace("-", " ").title() for s in segments]

    return " — ".join(label_parts) if label_parts else "General Platform"
