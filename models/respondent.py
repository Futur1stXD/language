"""Модель респондента"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Respondent(Base):
    __tablename__ = "respondents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String, nullable=True)
    language_code = Column(String(2), default="ru")
    consented = Column(Boolean, default=False)
    completed = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)  # Для перезапусков
    wave_id = Column(String, default="wave_1")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связь с ответами
    answers = relationship("Answer", back_populates="respondent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_user_wave", "user_id", "wave_id", "archived"),
    )
    
    def __repr__(self):
        return f"<Respondent(id={self.id}, user_id={self.user_id}, completed={self.completed})>"
