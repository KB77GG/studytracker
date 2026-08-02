"""Response headers for pages carrying private study capabilities."""

from flask import make_response


def no_store(response):
    """Prevent caching, referrer propagation, and indexing of private pages."""
    if not hasattr(response, "headers"):
        response = make_response(response)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
