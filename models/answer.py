"""Модель ответа на вопрос"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Answer(Base):
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    respondent_id = Column(Integer, ForeignKey("respondents.id", ondelete="CASCADE"), nullable=False)
    question_code = Column(String(10), nullable=False)  # Q1, Q2, etc.
    answer = Column(Text, nullable=False)  # JSON для мультивыбора, текст для остальных
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с респондентом
    respondent = relationship("Respondent", back_populates="answers")
    
    __table_args__ = (
        Index("idx_respondent_question", "respondent_id", "question_code"),
    )
    
    def __repr__(self):
        return f"<Answer(id={self.id}, question={self.question_code})>"
