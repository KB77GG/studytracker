# Gunicorn config for the standalone trial tool (test environment use).
# Always pass it explicitly:  gunicorn -c tools/ielts_writing_ai/gunicorn.conf.py ...
# Without -c, gunicorn would pick up the repository-root gunicorn.conf.py, which
# belongs to the main app (port 5002).
import os

bind = f"{os.environ.get('IWA_HOST', '127.0.0.1')}:{os.environ.get('IWA_PORT', '5055')}"
_data_dir = os.environ.get("IWA_DATA_DIR") or os.path.join(os.path.dirname(__file__), "var")
# Newer gunicorn opens a control socket under ~/.gunicorn by default; keep ours in the
# tool's own data dir so it can never collide with the main app's gunicorn.
control_socket = os.path.join(_data_dir, "gunicorn.ctl")
# One process: background generations run in-process and restart recovery
# assumes a single owner of the trial database.
workers = 1
worker_class = "gthread"
threads = 4
timeout = 60
graceful_timeout = 20
accesslog = "-"
errorlog = "-"
loglevel = "info"
wsgi_app = "tools.ielts_writing_ai.wsgi:app"
