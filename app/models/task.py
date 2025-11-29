from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_mixins import TimestampMixin

__all__ = ["TaskStatus", "Task", "TaskLink", "TaskActivity", "TaskHistory"]


class TaskStatus(Base):
    __tablename__ = "task_statuses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    color = Column(String, default="gray")  # blue, green, yellow, etc.
    is_final = Column(Boolean, default=False)  # Determines if task is "Done"

    tasks = relationship("Task", back_populates="status")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    slug = Column(
        String, unique=True, index=True, nullable=False
    )  # Ensure this exists from previous step

    description = Column(Text, nullable=True)

    # Changed: Boolean -> Foreign Key
    status_id = Column(Integer, ForeignKey("task_statuses.id"))

    # Added: For sorting "Late" items
    deadline = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    status = relationship("TaskStatus", back_populates="tasks")
    links = relationship(
        "TaskLink", back_populates="task", cascade="all, delete-orphan"
    )
    # Update this relationship to include order_by
    activities = relationship(
        "TaskActivity",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="desc(TaskActivity.created_at)",  # <--- Newest first
    )

    # Do the same for history if you like
    history = relationship(
        "TaskHistory",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="desc(TaskHistory.created_at)",
    )


class TaskLink(Base):
    __tablename__ = "task_links"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    name = Column(String)
    url = Column(String)
    task = relationship("Task", back_populates="links")


class TaskActivity(Base, TimestampMixin):
    """User Comments / Manual Logs"""

    __tablename__ = "task_activities"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    content = Column(Text)
    task = relationship("Task", back_populates="activities")


class TaskHistory(Base, TimestampMixin):
    """System Status Changes"""

    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))

    change_type = Column(String)  # STATUS, DEADLINE
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    remark = Column(Text, nullable=True)

    task = relationship("Task", back_populates="history")
