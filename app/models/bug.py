from sqlalchemy import (
    func,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_mixins import TimestampMixin


__all__ = ["BugStatus", "Bug", "BugLink", "BugActivity", "BugHistory"]


class BugStatus(Base):
    __tablename__ = "bug_statuses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    slug = Column(String, unique=True, index=True)

    color = Column(String, default="gray")
    # NEW: Flag to determine if this status stops the clock (e.g. Closed, Deployed)
    is_final = Column(Boolean, default=False)

    bugs = relationship("Bug", back_populates="status")


class Bug(Base, TimestampMixin):
    __tablename__ = "bugs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text)
    status_id = Column(Integer, ForeignKey("bug_statuses.id"))
    delivery_date = Column(DateTime(timezone=True), nullable=True)

    reported_at = Column(DateTime(timezone=True), server_default=func.now())

    status = relationship("BugStatus", back_populates="bugs")
    links = relationship("BugLink", back_populates="bug", cascade="all, delete-orphan")
    activities = relationship(
        "BugActivity",
        back_populates="bug",
        cascade="all, delete-orphan",
        order_by="desc(BugActivity.created_at)",  # <--- Newest first
    )

    history = relationship(
        "BugHistory", back_populates="bug", cascade="all, delete-orphan"
    )


class BugLink(Base):
    __tablename__ = "bug_links"
    id = Column(Integer, primary_key=True, index=True)
    bug_id = Column(Integer, ForeignKey("bugs.id"))
    name = Column(String)
    url = Column(String)
    bug = relationship("Bug", back_populates="links")


class BugActivity(Base, TimestampMixin):
    __tablename__ = "bug_activities"
    id = Column(Integer, primary_key=True, index=True)
    bug_id = Column(Integer, ForeignKey("bugs.id"))
    content = Column(Text)
    bug = relationship("Bug", back_populates="activities")


class BugHistory(Base, TimestampMixin):
    __tablename__ = "bug_history"
    id = Column(Integer, primary_key=True, index=True)
    bug_id = Column(Integer, ForeignKey("bugs.id"))
    change_type = Column(String)  # STATUS_CHANGE, DATE_CHANGE
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    remark = Column(Text, nullable=True)
    bug = relationship("Bug", back_populates="history")
