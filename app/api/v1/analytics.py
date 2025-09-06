from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database.connection import get_db
from app.services.ticket_service import TicketService
from app.services.ml_service import ml_service
from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    """Dependency to get ticket service"""
    return TicketService(db)

@router.get("/overview")
async def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get comprehensive analytics overview including ML insights"""
    
    # Get basic ticket stats
    basic_stats = ticket_service.get_ticket_stats(current_user.organization_id)
    
    # Get ML analytics
    ml_analytics = ticket_service.get_ml_analytics(current_user.organization_id)
    
    # Get ML system health
    ml_health = ml_service.get_health_status()
    
    return {
        "basic_stats": basic_stats,
        "ml_insights": ml_analytics,
        "ml_system": {
            "available": ml_health["available"],
            "components_status": ml_health["components"]
        },
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/categories")
async def get_category_analytics(
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get detailed category analytics with ML classification"""
    ml_analytics = ticket_service.get_ml_analytics(current_user.organization_id)
    
    return {
        "categories": ml_analytics.get("categories", {}),
        "categories_percentage": ml_analytics.get("categories_percentage", {}),
        "total_tickets": ml_analytics.get("total_tickets", 0),
        "analysis_timestamp": ml_analytics.get("processing_time", 0)
    }

@router.get("/sentiment")
async def get_sentiment_analytics(
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get sentiment analysis across all tickets"""
    ml_analytics = ticket_service.get_ml_analytics(current_user.organization_id)
    
    return {
        "sentiments": ml_analytics.get("sentiments", {}),
        "sentiments_percentage": ml_analytics.get("sentiments_percentage", {}),
        "total_tickets": ml_analytics.get("total_tickets", 0),
        "insights": {
            "most_common_sentiment": max(ml_analytics.get("sentiments", {}), key=ml_analytics.get("sentiments", {}).get, default="neutral"),
            "negative_ratio": ml_analytics.get("sentiments_percentage", {}).get("negative", 0)
        }
    }

@router.get("/trends")
async def get_trend_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get trend analysis for specified period"""
    ml_analytics = ticket_service.get_ml_analytics(current_user.organization_id)
    trends = ml_analytics.get("trends", {})
    
    return {
        "period_days": days,
        "trends": trends,
        "analysis_timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health")
async def get_ml_health_status() -> Dict[str, Any]:
    """Get ML system health and availability status"""
    return ml_service.get_health_status()

@router.get("/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get performance metrics for ML system"""
    
    # Get a small sample of tickets for performance testing
    sample_tickets = ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=None,
        page=1,
        size=10,
        sort_by="created_at",
        sort_order="desc"
    )
    
    performance_metrics = {
        "ml_system_available": ml_service.is_available,
        "sample_size": len(sample_tickets.items) if hasattr(sample_tickets, 'items') else 0,
        "components": ml_service.get_health_status()["components"],
        "benchmark_timestamp": datetime.utcnow().isoformat()
    }
    
    # If we have tickets, test performance on a sample
    if hasattr(sample_tickets, 'items') and sample_tickets.items:
        sample_ticket = sample_tickets.items[0]
        text = getattr(sample_ticket, 'content', getattr(sample_ticket, 'description', ''))
        
        if text and ml_service.is_available:
            # Time a classification
            start_time = datetime.utcnow()
            classification = ml_service.classify_ticket(text)
            classification_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Time a sentiment analysis
            start_time = datetime.utcnow()
            sentiment = ml_service.analyze_sentiment(text)
            sentiment_time = (datetime.utcnow() - start_time).total_seconds()
            
            performance_metrics.update({
                "classification_time_seconds": classification_time,
                "sentiment_time_seconds": sentiment_time,
                "sample_text_length": len(text),
                "classification_confidence": classification.get("confidence", 0),
                "sentiment_confidence": sentiment.get("confidence", 0)
            })
    
    return performance_metrics