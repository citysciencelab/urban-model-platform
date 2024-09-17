from sqlalchemy import BigInteger, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from dataclasses import dataclass

class Base(DeclarativeBase):
    pass

@dataclass
class Ensemble(Base):
    __tablename__ = "ensembles"

    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str] = mapped_column(String())
    description: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
    scenario_configs: Mapped[str] = mapped_column(String())

@dataclass
class Comment(Base):
    __tablename__ = 'ensemble_comments'

    id: Mapped[int] = mapped_column(primary_key = True)
    user_id: Mapped[str] = mapped_column(String())
    ensemble_id: Mapped[int] = mapped_column(BigInteger())
    comment: Mapped[str] = mapped_column(String())
