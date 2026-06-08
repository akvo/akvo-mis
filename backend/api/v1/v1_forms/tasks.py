from django.core.management import call_command


def refresh_form_config():
    """Clear the Django cache and regenerate config.min.js.

    Dispatched asynchronously after a form is published so the web form
    renderer and the frontend FormDropdown both see the updated form list
    without blocking the publish HTTP response.
    """
    call_command("clear_cache")
    call_command("generate_config")
