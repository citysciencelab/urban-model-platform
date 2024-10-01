from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from sqlalchemy_serializer import SerializerMixin

Base = declarative_base()

class JobsEnsembles(Base, SerializerMixin):
    __tablename__ = 'jobs_ensembles'

    id: Mapped[int] = mapped_column(primary_key=True)
    ensemble_id: Mapped[int] = mapped_column(BigInteger())
    job_id: Mapped[int] = mapped_column(String())

class Ensemble(Base, SerializerMixin):
    __tablename__ = "ensembles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String())
    description: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
    scenario_configs: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())
    jobs_metadata: ClassVar[dict]

    def __init__(
        self,
        name: str,
        description: str,
        user_id: str,
        scenario_configs: str,
    ):
        self.name = name
        self.description = description
        self.user_id = user_id
        self.scenario_configs = scenario_configs
        self.created = datetime.now(timezone.utc)
        self.modified = datetime.now(timezone.utc)

    def _to_dict(self):
        return {
            "id": self.id,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "scenario_configs": self.scenario_configs,
        }

class Comment(Base, SerializerMixin):
    __tablename__ = "ensemble_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String())
    ensemble_id: Mapped[int] = mapped_column(BigInteger(), ForeignKey("ensembles.id"))
    comment: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())

    def __init__(self, user_id: str, ensemble_id: int, comment: str):
        self.user_id = user_id
        self.ensemble_id = ensemble_id
        self.comment = comment
        self.created = datetime.now(datetime.timezone.utc)
        self.modified = datetime.now(datetime.timezone.utc)

    def _to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ensemble_id": self.ensemble_id,
            "comment": self.comment,
        }
