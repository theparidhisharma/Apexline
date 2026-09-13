"""SQLite schema (SQLAlchemy, Postgres-ready). Nothing is deletable — only decided."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (JSON, Boolean, Column, DateTime, Enum, Float,
                        ForeignKey, Integer, String, Text, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///data/apexline.db",
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def now():
    return dt.datetime.utcnow()


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    venue = Column(String)
    created_at = Column(DateTime, default=now)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    type = Column(Enum("practice", "quali", "race", name="session_type"), default="race")
    rule_profile = Column(JSON, default=dict)
    status = Column(String, default="created")
    started_at = Column(DateTime)
    ended_at = Column(DateTime)


class Corner(Base):
    __tablename__ = "corners"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    camera_source = Column(String)
    homography = Column(JSON)
    boundary_polyline = Column(JSON)
    boundary_reference = Column(Enum("white_line", "kerb_edge", "custom",
                                     name="boundary_ref"), default="white_line")
    calib_residual_px = Column(Float)
    calibrated_at = Column(DateTime)
    calib_version = Column(Integer, default=1)  # versioned + referenced by incidents


class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    display_number = Column(String)
    team = Column(String)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), index=True)
    corner_id = Column(Integer, ForeignKey("corners.id"))
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=True, index=True)
    track_id = Column(Integer)
    type_code = Column(String, default="V2")
    context_tags = Column(JSON, default=list)
    advantage_gained_s = Column(Float, nullable=True)
    t_start_ms = Column(Integer)
    t_end_ms = Column(Integer)
    max_overshoot_m = Column(Float)
    error_band_m = Column(Float)
    duration_ms = Column(Integer)
    confidence = Column(Float)
    band = Column(Enum("auto_clear", "needs_review", "auto_flag", name="band"), index=True)
    status = Column(Enum("pending", "approved", "rejected", "escalated",
                         name="status"), default="pending", index=True)
    decided_by = Column(String)
    decided_at = Column(DateTime)
    note = Column(Text)
    clip_path = Column(String)
    clip_sha256 = Column(String)
    calib_version = Column(Integer)
    explain = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)


class Penalty(Base):
    __tablename__ = "penalties"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    car_id = Column(Integer, ForeignKey("cars.id"))
    step = Column(String)
    triggered_by_incident_id = Column(Integer, ForeignKey("incidents.id"))
    issued_at = Column(DateTime, default=now)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=True)
    corner_id = Column(Integer, ForeignKey("corners.id"), nullable=True)
    t_ms = Column(Integer)
    kind = Column(Enum("pre_corner_prob", "strike_risk", name="pred_kind"))
    value = Column(Float)
    features = Column(JSON, default=dict)
    model_version = Column(String)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    actor = Column(String)
    action = Column(String)
    entity = Column(String)
    entity_id = Column(Integer)
    payload = Column(JSON, default=dict)
    at = Column(DateTime, default=now)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id = Column(Integer, primary_key=True)
    source_session = Column(String)
    official_events = Column(Integer)
    matched = Column(Integer)
    missed = Column(Integer)
    extra = Column(Integer)
    precision = Column(Float)
    recall = Column(Float)
    notes = Column(Text)
    at = Column(DateTime, default=now)


def init_db():
    Base.metadata.create_all(engine)
