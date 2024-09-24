from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


@dataclass
class Ensemble(Base):
    __tablename__ = "ensembles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String())
    description: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
    scenario_configs: Mapped[str] = mapped_column(String())
    sample_size: Mapped[int] = mapped_column(BigInteger())
    sampling_method: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())

    def _to_dict(self):
        return {
            "id": self.id,
            "created": self.created,
            "modified": self.modified,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "scenario_configs": self.scenario_configs,
            "sample_size": self.sample_size,
            "sampling_method": self.sampling_method,
        }


@dataclass
class Comment(Base):
    __tablename__ = "ensemble_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String())
    ensemble_id: Mapped[int] = mapped_column(BigInteger(), ForeignKey("ensembles.id"))
    comment: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())

    def _to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ensemble_id": self.ensemble_id,
            "comment": self.comment,
        }
