from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from typing import List, Optional
from datetime import datetime
import math

from app.core.database import get_db
from app.core.config import templates
from app.models.task import Task, TaskStatus, TaskHistory, TaskActivity, TaskLink
from app.utils import get_unique_slug

router = APIRouter()


@router.get("/")
async def list_tasks(
    request: Request,
    status: List[str] = Query(default=[]),
    search: Optional[str] = Query(None),
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    # 1. Status Counts
    status_counts = (
        db.query(TaskStatus.slug, func.count(Task.id))
        .join(Task)
        .group_by(TaskStatus.slug)
        .all()
    )

    count_map = {s_slug: count for s_slug, count in status_counts}

    all_statuses = db.query(TaskStatus).order_by(TaskStatus.id).all()
    total_tasks_count = 0
    for s in all_statuses:
        s.count = count_map.get(s.slug, 0)
        total_tasks_count += s.count

    # 2. Build Query
    # Use outerjoin to include tasks without activities
    query = db.query(Task).outerjoin(TaskActivity).join(TaskStatus)

    # --- SEARCH LOGIC (Word-by-Word OR) ---
    if search:
        search_words = search.strip().split()
        conditions = []

        for word in search_words:
            term = f"%{word}%"
            # Create a condition that checks this specific word against ALL fields
            conditions.append(
                or_(
                    Task.title.ilike(term),
                    Task.description.ilike(term),
                    TaskActivity.content.ilike(term),
                )
            )

        # Combine all word conditions with OR
        # This means: (Match Word 1) OR (Match Word 2) OR ...
        if conditions:
            query = query.filter(or_(*conditions))

        # Prevent duplicates if a task matches multiple words or has multiple logs
        query = query.distinct()
    # --------------------------------------

    # 3. Filter by Status (Keep existing)
    if status:
        # JOIN is already done above (.join(TaskStatus))
        query = query.filter(TaskStatus.slug.in_(status))

        if not search:
            # Calculate total from the map based on selected slugs
            total_items = sum(count_map.get(slug, 0) for slug in status)
        else:
            total_items = query.count()
    else:
        total_items = query.count() if search else total_tasks_count

    # 4. Sorting (Overdue > Active > Created)
    now = datetime.now()
    is_overdue = case(
        (and_(TaskStatus.is_final == False, Task.deadline < now), 1), else_=0
    )
    is_active = case((TaskStatus.is_final == False, 1), else_=0)

    query = query.order_by(
        is_overdue.desc(),
        Task.deadline.asc(),
        is_active.desc(),
        Task.created_at.asc(),
        Task.updated_at.desc(),
    )

    # 5. Pagination
    total_pages = math.ceil(total_items / limit) if limit > 0 else 1
    offset = (page - 1) * limit
    tasks = query.limit(limit).offset(offset).all()

    # Helper for URL params
    params_str = "".join([f"&status={s}" for s in status])

    if search:
        params_str += f"&search={search}"

    return templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "tasks": tasks,
            "statuses": all_statuses,
            "total_tasks": total_tasks_count,
            "current_status_slugs": status,
            "search_query": search,
            "params_str": params_str,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
    )


@router.get("/new")
async def new_task_form(request: Request, db: Session = Depends(get_db)):
    statuses = db.query(TaskStatus).all()
    return templates.TemplateResponse(
        "tasks/create.html", {"request": request, "statuses": statuses}
    )


@router.post("/create")
async def create_task(
    title: str = Form(...),
    description: str = Form(""),
    status_id: int = Form(...),
    deadline: str = Form(None),
    link_names: List[str] = Form([]),
    link_urls: List[str] = Form([]),
    db: Session = Depends(get_db),
):
    d_date = datetime.strptime(deadline, "%Y-%m-%d") if deadline else None

    slug = get_unique_slug(db, Task, title)
    new_task = Task(
        title=title,
        slug=slug,
        description=description,
        status_id=status_id,
        deadline=d_date,
    )
    db.add(new_task)
    db.flush()

    # Links
    for name, url in zip(link_names, link_urls):
        if url.strip():
            db.add(TaskLink(task_id=new_task.id, name=name, url=url))

    # Initial Log
    db.add(TaskActivity(task_id=new_task.id, content="Task created"))
    db.commit()

    return RedirectResponse(url="/tasks", status_code=303)


@router.get("/{slug}")
async def task_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    # Changed: Query by slug instead of get(id)
    task = db.query(Task).filter(Task.slug == slug).first()

    if not task:
        return RedirectResponse(url="/tasks")

    statuses = db.query(TaskStatus).all()

    # Split Logs (Comments vs History)
    history_logs = sorted(task.history, key=lambda x: x.created_at, reverse=True)
    activity_logs = sorted(task.activities, key=lambda x: x.created_at, reverse=True)

    return templates.TemplateResponse(
        "tasks/detail.html",
        {
            "request": request,
            "task": task,
            "statuses": statuses,
            "history_logs": history_logs,
            "activity_logs": activity_logs,
        },
    )


@router.post("/{task_id}/edit_details")
async def edit_task_details(
    task_id: int,
    title: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db),
):
    task = db.query(Task).get(task_id)
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)

    # Update fields
    task.title = title
    task.description = description

    # Log the update (optional, but good for tracking)
    db.add(
        TaskActivity(
            task_id=task.id, content="Updated task details (Title/Description)"
        )
    )

    db.commit()
    return RedirectResponse(url=f"/tasks/{task.slug}", status_code=303)


@router.post("/{task_id}/update")
async def update_task(
    task_id: int,
    status_id: int = Form(...),
    deadline: str = Form(None),
    remark: str = Form(None),
    db: Session = Depends(get_db),
):
    task = db.query(Task).get(task_id)

    # 1. Deadline Change
    new_date = datetime.strptime(deadline, "%Y-%m-%d") if deadline else None
    old_date_str = task.deadline.strftime("%Y-%m-%d") if task.deadline else "None"
    new_date_str = new_date.strftime("%Y-%m-%d") if new_date else "None"

    if old_date_str != new_date_str:
        db.add(
            TaskHistory(
                task_id=task.id,
                change_type="DEADLINE",
                old_value=old_date_str,
                new_value=new_date_str,
                remark=remark,
            )
        )
        task.deadline = new_date

    # 2. Status Change
    if task.status_id != status_id:
        old_status = db.query(TaskStatus).get(task.status_id)
        new_status = db.query(TaskStatus).get(status_id)
        db.add(
            TaskHistory(
                task_id=task.id,
                change_type="STATUS",
                old_value=old_status.name if old_status else "?",
                new_value=new_status.name,
                remark=remark,
            )
        )
        task.status_id = status_id

    db.commit()
    return RedirectResponse(url=f"/tasks/{task.slug}", status_code=303)


@router.post("/{task_id}/comment")
async def add_comment(
    task_id: int, content: str = Form(...), db: Session = Depends(get_db)
):
    task = db.query(Task).get(task_id)
    db.add(TaskActivity(task_id=task_id, content=content))
    db.commit()
    return RedirectResponse(url=f"/tasks/{task.slug}", status_code=303)


@router.post("/{task_id}/attach")
async def attach_link(
    task_id: int,
    name: str = Form(...),
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    if name and url:
        task = db.query(Task).get(task_id)
        db.add(TaskLink(task_id=task_id, name=name, url=url))
        db.commit()
    return RedirectResponse(url=f"/tasks/{task.slug}", status_code=303)
