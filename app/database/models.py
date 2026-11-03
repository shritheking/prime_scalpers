import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    VERIFIED = "VERIFIED"
    WRONG_AFFILIATE = "WRONG_AFFILIATE"
    DEPOSIT_REQUIRED = "DEPOSIT_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    RETRY_PENDING = "RETRY_PENDING"
    REJECTED = "REJECTED"


class RegistrationStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVITED = "INVITED"
    JOINED = "JOINED"


class ChallengeStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    full_name = Column(String(150), nullable=True)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    full_name = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    registrations = relationship("Registration", back_populates="participant", cascade="all, delete-orphan")


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    minimum_deposit = Column(Float, default=100.0, nullable=False)
    max_slots = Column(Integer, default=50, nullable=False)
    allocated_slots = Column(Integer, default=0, nullable=False)
    status = Column(SAEnum(ChallengeStatus), default=ChallengeStatus.OPEN, nullable=False)
    registration_deadline = Column(DateTime, nullable=True)
    affiliate_link_id = Column(String(50), default="2414647", nullable=False)
    invite_expiry_hours = Column(Integer, default=24, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    registrations = relationship("Registration", back_populates="challenge")

    @property
    def remaining_slots(self) -> int:
        return max(0, self.max_slots - self.allocated_slots)


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    quotex_trader_id = Column(String(50), nullable=False, index=True)
    account_type = Column(String(20), default="new", nullable=False)  # 'new' or 'existing'
    status = Column(SAEnum(RegistrationStatus), default=RegistrationStatus.SUBMITTED, nullable=False, index=True)
    verification_status = Column(SAEnum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False, index=True)
    slot_reserved = Column(Boolean, default=False, nullable=False)
    admin_notes = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_auto_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("participant_id", "challenge_id", name="uq_participant_challenge"),
    )

    participant = relationship("Participant", back_populates="registrations")
    challenge = relationship("Challenge", back_populates="registrations")
    verification_requests = relationship("VerificationRequest", back_populates="registration", cascade="all, delete-orphan")
    invite_links = relationship("InviteLink", back_populates="registration", cascade="all, delete-orphan")


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_id = Column(Integer, ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_name = Column(String(50), default="manual", nullable=False)
    status = Column(SAEnum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    registration = relationship("Registration", back_populates="verification_requests")
    results = relationship("VerificationResult", back_populates="request", cascade="all, delete-orphan")


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("verification_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    verified_by_admin_id = Column(BigInteger, nullable=True)  # Admin Telegram ID who performed verification
    trader_id = Column(String(50), nullable=False)
    affiliate_link_id = Column(String(50), nullable=True)
    deposit_amount = Column(Float, nullable=True)
    balance = Column(Float, nullable=True)
    deposits_count = Column(Integer, nullable=True)
    withdrawals_count = Column(Integer, nullable=True)
    withdrawals_sum = Column(Float, nullable=True)
    country = Column(String(100), nullable=True)
    registration_date = Column(String(50), nullable=True)
    is_affiliate_matched = Column(Boolean, default=False, nullable=False)
    is_deposit_sufficient = Column(Boolean, default=False, nullable=False)
    raw_evidence = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("VerificationRequest", back_populates="results")


class InviteLink(Base):
    __tablename__ = "invite_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_id = Column(Integer, ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_telegram_id = Column(BigInteger, nullable=False, index=True)
    invite_link = Column(String(255), nullable=False, unique=True)
    member_limit = Column(Integer, default=1, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    registration = relationship("Registration", back_populates="invite_links")


class ChannelMember(Base):
    __tablename__ = "channel_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id", ondelete="SET NULL"), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(30), default="member", nullable=False)  # 'member', 'left', 'kicked'
    is_authorized = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("channel_id", "telegram_id", name="uq_channel_telegram_user"),
    )


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    target_challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True)
    total_targets = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    fail_count = Column(Integer, default=0, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id = Column(BigInteger, nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
