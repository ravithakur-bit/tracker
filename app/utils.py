import re
from datetime import datetime, timezone
import markdown  # type: ignore
from markupsafe import Markup
from slugify import slugify
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta


def days_until(date_obj):
    """Calculates days from now until target date. Negative means late."""
    if not date_obj:
        return None
    # Ensure timezone awareness matches your DB (usually UTC or local)
    now = datetime.now(timezone.utc) if date_obj.tzinfo else datetime.now()
    delta = date_obj - now
    return delta.days


def days_since(date_obj):
    """Calculates age in days."""
    if not date_obj:
        return 0
    now = datetime.now(timezone.utc) if date_obj.tzinfo else datetime.now()
    delta = now - date_obj
    return delta.days


def markdown_filter(text):
    if not text:
        return ""

    return markdown.markdown(text, extensions=["fenced_code", "nl2br", "tables"])


def highlight_filter(text, search_query):
    """
    Wraps search terms in <mark> tags.
    Handles multiple words and case-insensitivity.
    """
    if not text or not search_query:
        return text

    # Split search query into words and remove empty strings
    words = [w for w in search_query.strip().split() if w]
    if not words:
        return text

    # Create regex pattern: (word1|word2|word3)
    # re.escape ensures special characters like '?' don't break regex
    pattern_str = "|".join(re.escape(w) for w in words)
    pattern = re.compile(f"({pattern_str})", re.IGNORECASE)

    # Replacement function
    def replace(match):
        # Apply Tailwind classes for highlighting
        return f'<mark class="bg-yellow-200 dark:bg-yellow-500/30 dark:text-yellow-100 rounded-sm px-0.5 font-medium">{match.group(0)}</mark>'

    # Perform replacement
    highlighted = pattern.sub(replace, str(text))

    # Return as safe HTML so Jinja renders the tags
    return Markup(highlighted)


def local_time_filter(date_obj):
    """
    Renders a span with raw UTC data.
    JS picks this up and converts it to local time.
    Handles naive datetimes from SQLite by appending 'Z'.
    """
    if not date_obj:
        return ""

    # SQLite returns naive datetimes. We must treat them as UTC.
    iso_str = date_obj.isoformat()
    if date_obj.tzinfo is None:
        iso_str += "Z"  # Force UTC interpretation

    return Markup(
        f'<span class="datetime-local opacity-0 transition-opacity duration-300" '
        f'data-utc="{iso_str}">'
        f"{date_obj.strftime('%d %b %Y, %H:%M')} UTC"  # Fallback
        f"</span>"
    )


def time_ago_filter(date_obj):
    """
    Returns a string representing how much time has passed.
    e.g. '10 sec old', '5 min old', '2 hr old', '3 days old'
    """
    if not date_obj:
        return ""

    # Handle SQLite naive dates (Assume they are UTC)
    now = datetime.utcnow()
    diff = now - date_obj

    seconds = diff.total_seconds()

    if seconds < 60:
        return f"{int(seconds)} sec old"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} min old"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hr old"
    elif seconds < 2592000:  # Approx 30 days
        return f"{diff.days} days old"
    elif seconds < 31536000:  # Approx 365 days
        months = int(diff.days // 30)
        return f"{months} mo old"
    else:
        years = int(diff.days // 365)
        return f"{years} yr old"


def get_unique_slug(db: Session, model: DeclarativeMeta, title: str) -> str:
    """
    Generates a URL-safe slug using python-slugify.
    Checks the database to ensure uniqueness by appending -1, -2, etc.
    """
    base_slug = slugify(title)
    slug = base_slug
    counter = 1

    # Check if slug exists in the specific model table
    while db.query(model).filter(model.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug
