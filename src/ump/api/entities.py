from __future__ import annotations

from datetime import datetime
from typing import List
from sqlalchemy import BigInteger, Column, ForeignKey, String, DateTime, Table
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship, declarative_base
from sqlalchemy_serializer import SerializerMixin

Base = declarative_base()

job_configs_ensembles = Table(
    'job_configs_ensembles',
    Base.metadata,
    Column('ensemble_id', BigInteger(), ForeignKey('ensembles.id'), primary_key=True),
    Column('job_config_id', BigInteger(), ForeignKey('job_configs.id'), primary_key=True),
)

class Ensemble(Base, SerializerMixin):
    __tablename__ = 'ensembles'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key = True)
    name: Mapped[str] = mapped_column(String())
    description: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
    scenario_configs: Mapped[str] = mapped_column(String())
    created: Mapped[datetime] = mapped_column(DateTime())
    modified: Mapped[datetime] = mapped_column(DateTime())
    job_configs: Mapped[List[JobConfig]] = relationship(
        secondary=job_configs_ensembles, back_populates='ensembles'
    )

class Comment(Base, SerializerMixin):
    __tablename__ = 'ensemble_comments'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key = True)
    user_id: Mapped[str] = mapped_column(String())
    ensemble_id: Mapped[int] = mapped_column(BigInteger())
    comment: Mapped[str] = mapped_column(String())

class JobConfig(Base, SerializerMixin):
    __tablename__ = 'job_configs'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key = True)
    process_id: Mapped[str] = mapped_column(String())
    provider_prefix: Mapped[str] = mapped_column(String())
    provider_url: Mapped[str] = mapped_column(String())
    message: Mapped[str] = mapped_column(String())
    parameters: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
    process_title: Mapped[str] = mapped_column(String())
    name: Mapped[str] = mapped_column(String())
    ensembles: Mapped[List[Ensemble]] = relationship(
        secondary=job_configs_ensembles, back_populates='job_configs'
    )

class JobExecution(Base, SerializerMixin):
    __tablename__ = 'job_executions'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key = True)
    job_config_id: Mapped[int] = mapped_column(BigInteger())
    job_id: Mapped[str] = mapped_column(String())
    remote_job_id: Mapped[str] = mapped_column(String())
    status: Mapped[str] = mapped_column(String())
    message: Mapped[str] = mapped_column(String())
    created = mapped_column(DateTime())
    started = mapped_column(DateTime())
    finished = mapped_column(DateTime())
    updated = mapped_column(DateTime())
    progress: Mapped[int] = mapped_column(BigInteger())
    results_metadata: Mapped[str] = mapped_column(String())
    user_id: Mapped[str] = mapped_column(String())
