import math
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import templates
from app.models.bug import Bug, BugStatus, BugHistory, BugActivity, BugLink
from app.utils import get_unique_slug

router = APIRouter()


@router.get("/")
async def list_bugs(
    request: Request,
    status: List[str] = Query(default=[]),
    search: Optional[str] = Query(None),  # Added Search Param
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    # 1. Status Counts
    status_counts = (
        db.query(BugStatus.slug, func.count(Bug.id))
        .join(Bug)
        .group_by(BugStatus.slug)
        .all()
    )

    # Map: {'in-progress': 5, 'to-do': 2}
    count_map = {s_slug: count for s_slug, count in status_counts}

    all_statuses = db.query(BugStatus).order_by(BugStatus.id).all()
    total_bugs_count = 0
    for s in all_statuses:
        s.count = count_map.get(s.slug, 0)
        total_bugs_count += s.count

    # 2. Build Query (Outerjoin Activity for Search)
    query = db.query(Bug).outerjoin(BugActivity).join(BugStatus)

    # --- SEARCH LOGIC (Word-by-Word OR) ---
    if search:
        search_words = search.strip().split()
        conditions = []

        for word in search_words:
            term = f"%{word}%"
            # Match Title OR Description OR Activity Content
            conditions.append(
                or_(
                    Bug.title.ilike(term),
                    Bug.description.ilike(term),
                    BugActivity.content.ilike(term),
                )
            )

        if conditions:
            query = query.filter(or_(*conditions))

        query = query.distinct()
    # --------------------------------------

    # 3. Status Filtering
    if status:
        # JOIN is already done above (.join(TaskStatus))
        query = query.filter(BugStatus.slug.in_(status))

        if not search:
            # Calculate total from the map based on selected slugs
            total_items = sum(count_map.get(slug, 0) for slug in status)
        else:
            total_items = query.count()
    else:
        total_items = query.count() if search else total_bugs_count

    # 4. Sorting
    now = datetime.now()
    is_overdue = case(
        (and_(BugStatus.is_final == False, Bug.delivery_date < now), 1), else_=0
    )
    is_active = case((BugStatus.is_final == False, 1), else_=0)

    query = query.order_by(
        is_overdue.desc(),
        Bug.delivery_date.asc(),
        is_active.desc(),
        Bug.created_at.asc(),
        Bug.updated_at.desc(),
    )

    # 5. Pagination
    total_pages = math.ceil(total_items / limit) if limit > 0 else 1
    offset = (page - 1) * limit
    bugs = query.limit(limit).offset(offset).all()

    # Params Helper
    params_str = "".join([f"&status={s}" for s in status])
    if search:
        params_str += f"&search={search}"

    return templates.TemplateResponse(
        "bugs/list.html",
        {
            "request": request,
            "bugs": bugs,
            "statuses": all_statuses,
            "total_bugs": total_bugs_count,
            "current_status_slugs": status,
            "search_query": search,  # Pass query to template
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
async def new_bug_form(request: Request, db: Session = Depends(get_db)):
    statuses = db.query(BugStatus).all()
    return templates.TemplateResponse(
        "bugs/create.html", {"request": request, "statuses": statuses}
    )


@router.post("/create")
async def create_bug(
    title: str = Form(...),
    description: str = Form(...),
    status_id: int = Form(...),
    delivery_date: str = Form(None),
    reported_at: str = Form(None),  # <--- New Param (datetime-local string)
    link_names: List[str] = Form([]),
    link_urls: List[str] = Form([]),
    db: Session = Depends(get_db),
):
    # Parse dates
    d_date = datetime.strptime(delivery_date, "%Y-%m-%d") if delivery_date else None

    # Parse Reported At (Format from HTML datetime-local is YYYY-MM-DDTHH:MM)
    r_date = None
    if reported_at:
        r_date = datetime.strptime(reported_at, "%Y-%m-%dT%H:%M").astimezone(
            tz=timezone.utc
        )
    else:
        r_date = datetime.now(tz=timezone.utc)  # Default to now if empty

    slug = get_unique_slug(db, Bug, title)
    new_bug = Bug(
        title=title,
        slug=slug,
        description=description,
        status_id=status_id,
        delivery_date=d_date,
        reported_at=r_date,  # <--- Save it
    )
    db.add(new_bug)
    db.flush()

    # Add Links
    for name, url in zip(link_names, link_urls):
        if url.strip():
            db.add(BugLink(bug_id=new_bug.id, name=name, url=url))

    # Initial Log
    # We use the reported date for the initial log timestamp too, to keep history clean
    db.add(BugActivity(bug_id=new_bug.id, content="Bug Created", created_at=r_date))

    db.commit()
    return RedirectResponse(url="/bugs", status_code=303)


@router.get("/{slug}")
async def bug_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    # Changed: Query by slug
    bug = db.query(Bug).filter(Bug.slug == slug).first()

    if not bug:
        return RedirectResponse(url="/bugs")

    statuses = db.query(BugStatus).all()

    # Sort logs
    history_logs = sorted(bug.history, key=lambda x: x.created_at, reverse=True)
    activity_logs = sorted(bug.activities, key=lambda x: x.created_at, reverse=True)

    return templates.TemplateResponse(
        "bugs/detail.html",
        {
            "request": request,
            "bug": bug,
            "statuses": statuses,
            "history_logs": history_logs,
            "activity_logs": activity_logs,
        },
    )


@router.post("/{bug_id}/edit_details")
async def edit_bug_details(
    bug_id: int,
    title: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db),
):
    bug = db.query(Bug).get(bug_id)
    if not bug:
        return RedirectResponse(url="/bugs", status_code=303)

    # Update fields
    bug.title = title
    bug.description = description

    # Log the update
    db.add(
        BugActivity(bug_id=bug.id, content="Updated bug details (Title/Description)")
    )

    db.commit()
    # Redirect to slug
    return RedirectResponse(url=f"/bugs/{bug.slug}", status_code=303)


@router.post("/{bug_id}/update")
async def update_bug(
    bug_id: int,
    status_id: int = Form(...),
    delivery_date: str = Form(None),
    remark: str = Form(None),
    db: Session = Depends(get_db),
):
    bug = db.query(Bug).get(bug_id)

    # 1. Date Logic
    new_date = datetime.strptime(delivery_date, "%Y-%m-%d") if delivery_date else None
    old_date_str = (
        bug.delivery_date.strftime("%Y-%m-%d") if bug.delivery_date else "None"
    )
    new_date_str = new_date.strftime("%Y-%m-%d") if new_date else "None"

    if old_date_str != new_date_str:
        db.add(
            BugHistory(
                bug_id=bug.id,
                change_type="DATE",
                old_value=old_date_str,
                new_value=new_date_str,
                remark=remark,
            )
        )
        bug.delivery_date = new_date

    # 2. Status Logic
    if bug.status_id != status_id:
        old_status = db.query(BugStatus).get(bug.status_id)
        new_status = db.query(BugStatus).get(status_id)
        db.add(
            BugHistory(
                bug_id=bug.id,
                change_type="STATUS",
                old_value=old_status.name if old_status else "?",
                new_value=new_status.name,
                remark=remark,
            )
        )
        bug.status_id = status_id

    db.commit()
    return RedirectResponse(url=f"/bugs/{bug.slug}", status_code=303)


@router.post("/{bug_id}/comment")
async def add_comment(
    bug_id: int, content: str = Form(...), db: Session = Depends(get_db)
):
    bug = db.query(Bug).get(bug_id)
    db.add(BugActivity(bug_id=bug_id, content=content))
    db.commit()
    return RedirectResponse(url=f"/bugs/{bug.slug}", status_code=303)


@router.post("/{bug_id}/attach")
async def attach_link(
    bug_id: int,
    name: str = Form(...),
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Adds a new link attachment to an existing bug
    """
    bug = db.query(Bug).get(bug_id)
    if name and url:
        link = BugLink(bug_id=bug_id, name=name, url=url)
        db.add(link)
        db.commit()

    return RedirectResponse(url=f"/bugs/{bug.slug}", status_code=303)
