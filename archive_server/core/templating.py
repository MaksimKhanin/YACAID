"""Single Jinja2 environment shared by core and feature modules.

Templates live under archive_server/templates/, with each module keeping its own
subdirectory (e.g. templates/security/...) while extending the shared base.html/login.html.
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
