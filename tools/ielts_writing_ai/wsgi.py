"""WSGI entry for gunicorn: ``gunicorn -c tools/ielts_writing_ai/gunicorn.conf.py``."""

from . import create_app

app = create_app()
