"""Comments for jobs."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column
from sqlalchemy_serializer import SerializerMixin

Base = declarative_base()

class JobComment(Base, SerializerMixin):
    """Comments for jobs."""
    __tablename__ = "job_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String())
    job_id: Mapped[str] = mapped_column(String())
    comment: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())
