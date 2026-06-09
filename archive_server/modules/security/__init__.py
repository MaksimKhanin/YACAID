"""Security module: camera archive, AI/motion alerts and remote camera control.

Its data (Media) is shared across the whole household — every logged-in user sees
the same cameras and alerts, unlike per-user module data (e.g. finance, diet).
"""
from archive_server.core.nav import NavItem
from archive_server.modules.security.ingest import router as ingest_router
from archive_server.modules.security.routes_control import router as control_router
from archive_server.modules.security.routes_ui import router as ui_router

routers = [ui_router, control_router, ingest_router]

nav_items = [
    NavItem(slug="cameras", label="Охрана", icon="🛡", url="/cameras"),
    NavItem(slug="alerts", label="Тревоги", icon="⚠", url="/alerts"),
    NavItem(slug="archive", label="Архив", icon="🗂", url="/archive"),
]
