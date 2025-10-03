"""
Classification Result Model - Stores ML classification results for tickets
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class ClassificationResult(Base):
    """Model to store ML classification results for tickets"""

    __tablename__ = "classification_results"

    # Relationships
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    ticket = relationship("Ticket", backref="classification_results")

    # Classification results
    category = Column(String(100), nullable=True, index=True)
    urgency = Column(String(50), nullable=True, index=True)
    sentiment = Column(String(50), nullable=True, index=True)

    # Confidence and metadata
    confidence_score = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    processing_time = Column(Float, nullable=True)  # in seconds

    # Additional metadata as JSON
    classification_metadata = Column(JSON, nullable=True, default=dict)

    # Timestamps
    classified_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ClassificationResult(ticket_id={self.ticket_id}, category='{self.category}', confidence={self.confidence_score})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "category": self.category,
            "urgency": self.urgency,
            "sentiment": self.sentiment,
            "confidence_score": self.confidence_score,
            "model_version": self.model_version,
            "processing_time": self.processing_time,
            "metadata": self.classification_metadata,
            "classified_at": self.classified_at.isoformat() if self.classified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
