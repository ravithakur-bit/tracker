import uvicorn
from slugify import slugify
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import SessionLocal
from app.routers import home, bugs, tasks
from app.models import bug, task

from contextlib import asynccontextmanager


def seed_data():
    db = SessionLocal()

    # --- 1. BUG STATUSES ---
    # Define the list based on your requirements
    # Format: (Name, Color, is_final)
    bug_definitions = [
        {"name": "Open", "color": "red", "is_final": False},
        {"name": "Reopened", "color": "orange", "is_final": False},
        {"name": "On Dev", "color": "blue", "is_final": False},
        {"name": "Query Sent", "color": "indigo", "is_final": False},
        {"name": "Query Answered", "color": "violet", "is_final": False},
        {"name": "On QA", "color": "yellow", "is_final": False},
        # Final States
        {"name": "On UAT", "color": "cyan", "is_final": True},
        {"name": "On Prod", "color": "emerald", "is_final": True},
        {"name": "Resolved", "color": "teal", "is_final": True},
        {"name": "Closed", "color": "green", "is_final": True},
        {"name": "On HOLD", "color": "gray", "is_final": True},
        {"name": "Resolved Duplicate", "color": "zinc", "is_final": True},
    ]

    for s in bug_definitions:
        slug = slugify(s["name"])
        # Check if status exists by slug to prevent duplicates
        existing = db.query(bug.BugStatus).filter(bug.BugStatus.slug == slug).first()

        if not existing:
            s["slug"] = slug
            db.add(bug.BugStatus(**s))
        else:
            # Optional: Update existing flags/colors if they changed
            existing.is_final = s["is_final"]
            existing.color = s["color"]

    # --- 2. TASK STATUSES ---
    task_definitions = [
        {"name": "Open", "color": "blue", "is_final": False},
        {"name": "In Progress", "color": "yellow", "is_final": False},
        {"name": "Reopened", "color": "purple", "is_final": False},
        # Final States
        {"name": "Closed", "color": "green", "is_final": True},
        {"name": "Discarded", "color": "slate", "is_final": True},
    ]

    for s in task_definitions:
        slug = slugify(s["name"])
        existing = (
            db.query(task.TaskStatus).filter(task.TaskStatus.slug == slug).first()
        )

        if not existing:
            s["slug"] = slug
            db.add(task.TaskStatus(**s))
        else:
            existing.is_final = s["is_final"]
            existing.color = s["color"]

    db.commit()
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_data()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home.router)
app.include_router(bugs.router, prefix="/bugs", tags=["Bugs"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.APP_PORT,
        reload=settings.APP_ENV.lower() == "dev",
    )
