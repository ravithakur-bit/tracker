from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, timedelta

from app.core.config import templates
from app.core.database import get_db
from app.models.task import Task, TaskStatus, TaskActivity
from app.models.bug import Bug, BugStatus, BugActivity

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # --- 1. FETCH RAW DATA ---
    active_tasks = (
        db.query(Task).join(TaskStatus).filter(TaskStatus.is_final == False).all()
    )
    active_bugs = (
        db.query(Bug).join(BugStatus).filter(BugStatus.is_final == False).all()
    )

    # --- 2. KPI CALCULATIONS ---
    stats = {
        "tasks_pending": len(active_tasks),
        "bugs_open": len(active_bugs),
        "due_today": 0,
        "overdue": 0,
    }

    # --- 3. FOCUS ZONE (Urgent Items) ---
    urgent_items = []

    def process_item(item, type_str, date_attr):
        target_dt = getattr(item, date_attr)
        if not target_dt:
            return

        target_date = target_dt.date()

        # Logic: Overdue OR Due Today OR Due Tomorrow
        if target_date <= tomorrow:
            label = "Upcoming"
            color = "blue"

            if target_date < today:
                stats["overdue"] += 1
                label = "Overdue"
                color = "red"
            elif target_date == today:
                stats["due_today"] += 1
                label = "Due Today"
                color = "orange"

            urgent_items.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "type": type_str,  # 'Task' or 'Bug'
                    "status": item.status.name,
                    "status_color": item.status.color,
                    "date": target_dt,
                    "label": label,
                    "label_color": color,
                    # LINK FIXED: Using slug
                    "link": f"/{'tasks' if type_str == 'Task' else 'bugs'}/{item.slug}",
                }
            )

    for t in active_tasks:
        process_item(t, "Task", "deadline")
    for b in active_bugs:
        process_item(b, "Bug", "delivery_date")

    # Sort by Date (Oldest/Most Urgent first)
    urgent_items.sort(key=lambda x: x["date"])

    # --- 4. CHART DATA (Status Distribution) ---
    def get_chart_data(model, status_model):
        results = (
            db.query(status_model.name, status_model.color, func.count(model.id))
            .join(model)
            .group_by(status_model.name)
            .all()
        )
        return {
            "labels": [r[0] for r in results],
            "colors": [r[1] for r in results],
            "counts": [r[2] for r in results],
        }

    chart_tasks = get_chart_data(Task, TaskStatus)
    chart_bugs = get_chart_data(Bug, BugStatus)

    # --- 5. UNIFIED ACTIVITY STREAM ---
    # Fetch last 10 of each
    t_logs = (
        db.query(TaskActivity).order_by(TaskActivity.created_at.desc()).limit(10).all()
    )
    b_logs = (
        db.query(BugActivity).order_by(BugActivity.created_at.desc()).limit(10).all()
    )

    activities = []
    for l in t_logs:
        activities.append(
            {
                "content": l.content,
                "time": l.created_at,
                "type": "Task",
                "parent_title": l.task.title,
                # LINK FIXED: Used l.task.slug instead of l.task_id
                "link": f"/tasks/{l.task.slug}",
            }
        )
    for l in b_logs:
        activities.append(
            {
                "content": l.content,
                "time": l.created_at,
                "type": "Bug",
                "parent_title": l.bug.title,
                # LINK FIXED: Used l.bug.slug instead of l.bug_id
                "link": f"/bugs/{l.bug.slug}",
            }
        )

    # Merge and Sort desc, take top 10
    activities.sort(key=lambda x: x["time"], reverse=True)
    activities = activities[:10]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "urgent_items": urgent_items,
            "activities": activities,
            "chart_data": {"tasks": chart_tasks, "bugs": chart_bugs},
        },
    )
