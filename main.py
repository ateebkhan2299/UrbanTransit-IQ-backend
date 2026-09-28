import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Root directory first so the top-level `database/` package resolves; the
# backend directory is appended so `backend.routers.*` stays importable.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(1, ROOT_DIR)

from backend.routers import admin_management, auth, comparison, dashboard  # noqa: E402
from backend.routers import delays, forecast, health, map as map_router  # noqa: E402
from backend.routers import notifications, occupancy, recommendations  # noqa: E402
from backend.routers import reports, routes, whatif  # noqa: E402

app = FastAPI(
    title="UrbanTransit IQ API",
    version="1.0",
    description=(
        "Big Data + Data Science API for public transport analytics. "
        "Serves Spark MLlib and Python Data Science pipeline results."
    ),
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# `allow_origins=["*"]` together with `allow_credentials=True` is rejected by
# browsers and violates the CORS spec, so the allowed origins are read from
# CORS_ORIGINS with an explicit local-dev default list.
DEFAULT_ORIGINS = [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'http://127.0.0.1:4173',
    'http://localhost:4173',
]
_cors = [o.strip() for o in os.getenv('CORS_ORIGINS', ','.join(DEFAULT_ORIGINS)).split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'],
)


@app.get('/')
def read_root():
    return {
        'message': 'UrbanTransit IQ API is running',
        'version': '1.0',
        'docs': '/docs',
        'charts': '/api/charts',
    }


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(auth.admin_router)
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(delays.router)
app.include_router(occupancy.router)
app.include_router(forecast.router)
app.include_router(map_router.router)
app.include_router(notifications.router)
app.include_router(admin_management.router)
app.include_router(recommendations.router)
app.include_router(whatif.router)
app.include_router(comparison.router)
app.include_router(reports.router)
app.include_router(routes.router)

# Static files: charts rendered by analysis/generate_charts.py
charts_dir = os.path.abspath(os.path.join(ROOT_DIR, 'documentation', 'charts'))
if os.path.exists(charts_dir):
    app.mount('/api/charts', StaticFiles(directory=charts_dir), name='charts')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
