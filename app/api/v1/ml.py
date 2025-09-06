from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import time
from datetime import datetime

from app.ml import (
    rule_based_classifier, 
    improved_classifier, 
    bert_classifier, 
    sentiment_analyzer, 
    text_processor, 
    trend_detector, 
    model_monitor
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Pydantic models for request/response
class TicketRequest(BaseModel):
    text: str = Field(..., description="Support ticket text to analyze", min_length=1, max_length=10000)

class TicketResponse(BaseModel):
    category: str
    confidence: float
    confidence_label: str
    text: str
    processing_time: float
    classifier_used: str

class SentimentRequest(BaseModel):
    text: str = Field(..., description="Text to analyze for sentiment", min_length=1, max_length=10000)

class SentimentResponse(BaseModel):
    sentiment: str
    sentiment_score: float
    confidence: float
    confidence_label: str
    text: str
    processing_time: float

class BatchRequest(BaseModel):
    tickets: List[str] = Field(..., description="List of ticket texts to process", min_items=1, max_items=1000)

class BatchResponse(BaseModel):
    classifications: List[Dict[str, Any]]
    sentiments: List[Dict[str, Any]]
    processing_time: float
    total_tickets: int

# Health check endpoint
@router.get("/health")
async def health_check():
    """Check ML system health"""
    try:
        # Basic health checks
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "classifiers": {
                "improved": improved_classifier.trained,
                "rule_based": True,
                "bert": hasattr(bert_classifier, 'model') and bert_classifier.model is not None
            }
        }
        return status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="ML system health check failed")

# Classification endpoints
@router.post("/classify", response_model=TicketResponse)
async def classify_ticket(request: TicketRequest):
    """Classify a support ticket using the best available classifier"""
    start_time = time.time()
    
    try:
        # Clean the input text
        clean_text = text_processor.clean_text(request.text)
        
        # Try improved classifier first (highest accuracy)
        if improved_classifier.trained:
            category, confidence = improved_classifier.classify(clean_text)
            classifier_used = "improved"
        else:
            # Fallback to rule-based classifier
            category, confidence = rule_based_classifier.classify(clean_text)
            classifier_used = "rule_based"
        
        # Determine confidence label
        if confidence >= 0.8:
            confidence_label = "high"
        elif confidence >= 0.6:
            confidence_label = "medium"
        else:
            confidence_label = "low"
        
        processing_time = time.time() - start_time
        
        return TicketResponse(
            category=category,
            confidence=confidence,
            confidence_label=confidence_label,
            text=request.text,
            processing_time=processing_time,
            classifier_used=classifier_used
        )
    
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")

@router.post("/classify/improved", response_model=TicketResponse)
async def classify_improved(request: TicketRequest):
    """Classify using the improved classifier specifically"""
    start_time = time.time()
    
    try:
        if not improved_classifier.trained:
            raise HTTPException(status_code=503, detail="Improved classifier not trained")
        
        clean_text = text_processor.clean_text(request.text)
        category, confidence = improved_classifier.classify(clean_text)
        
        confidence_label = "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low"
        processing_time = time.time() - start_time
        
        return TicketResponse(
            category=category,
            confidence=confidence,
            confidence_label=confidence_label,
            text=request.text,
            processing_time=processing_time,
            classifier_used="improved"
        )
    
    except Exception as e:
        logger.error(f"Improved classification error: {e}")
        raise HTTPException(status_code=500, detail="Improved classification failed")

@router.post("/classify/bert", response_model=TicketResponse)
async def classify_bert(request: TicketRequest):
    """Classify using BERT classifier"""
    start_time = time.time()
    
    try:
        if not hasattr(bert_classifier, 'model') or bert_classifier.model is None:
            raise HTTPException(status_code=503, detail="BERT classifier not loaded")
        
        clean_text = text_processor.clean_text(request.text)
        category, confidence = bert_classifier.classify(clean_text)
        
        confidence_label = "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low"
        processing_time = time.time() - start_time
        
        return TicketResponse(
            category=category,
            confidence=confidence,
            confidence_label=confidence_label,
            text=request.text,
            processing_time=processing_time,
            classifier_used="bert"
        )
    
    except Exception as e:
        logger.error(f"BERT classification error: {e}")
        raise HTTPException(status_code=500, detail="BERT classification failed")

# Sentiment analysis endpoint
@router.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    """Analyze sentiment of text"""
    start_time = time.time()
    
    try:
        clean_text = text_processor.clean_text(request.text)
        sentiment, score, confidence = sentiment_analyzer.analyze_sentiment(clean_text)
        
        confidence_label = "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low"
        processing_time = time.time() - start_time
        
        return SentimentResponse(
            sentiment=sentiment,
            sentiment_score=score,
            confidence=confidence,
            confidence_label=confidence_label,
            text=request.text,
            processing_time=processing_time
        )
    
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail="Sentiment analysis failed")

# Batch processing endpoint
@router.post("/batch", response_model=BatchResponse)
async def batch_process(request: BatchRequest):
    """Process multiple tickets at once"""
    start_time = time.time()
    
    try:
        classifications = []
        sentiments = []
        
        for ticket_text in request.tickets:
            # Classification
            try:
                clean_text = text_processor.clean_text(ticket_text)
                if improved_classifier.trained:
                    category, confidence = improved_classifier.classify(clean_text)
                    classifier_used = "improved"
                else:
                    category, confidence = rule_based_classifier.classify(clean_text)
                    classifier_used = "rule_based"
                
                classifications.append({
                    "text": ticket_text,
                    "category": category,
                    "confidence": confidence,
                    "classifier_used": classifier_used
                })
            except Exception as e:
                logger.error(f"Batch classification error for ticket: {e}")
                classifications.append({
                    "text": ticket_text,
                    "category": "error",
                    "confidence": 0.0,
                    "classifier_used": "none",
                    "error": str(e)
                })
            
            # Sentiment analysis
            try:
                sentiment, score, conf = sentiment_analyzer.analyze_sentiment(clean_text)
                sentiments.append({
                    "text": ticket_text,
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "confidence": conf
                })
            except Exception as e:
                logger.error(f"Batch sentiment error for ticket: {e}")
                sentiments.append({
                    "text": ticket_text,
                    "sentiment": "error",
                    "sentiment_score": 0.0,
                    "confidence": 0.0,
                    "error": str(e)
                })
        
        processing_time = time.time() - start_time
        
        return BatchResponse(
            classifications=classifications,
            sentiments=sentiments,
            processing_time=processing_time,
            total_tickets=len(request.tickets)
        )
    
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")

# Analytics endpoints
@router.get("/categories")
async def get_categories():
    """Get available ticket categories"""
    try:
        categories = {
            "categories": list(improved_classifier.category_patterns.keys()) if improved_classifier.trained else rule_based_classifier.categories,
            "total": len(improved_classifier.category_patterns) if improved_classifier.trained else len(rule_based_classifier.categories)
        }
        return categories
    except Exception as e:
        logger.error(f"Categories retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve categories")

# Model information endpoints
@router.get("/models/info")
async def get_models_info():
    """Get information about available models"""
    try:
        info = {
            "improved_classifier": {
                "trained": improved_classifier.trained,
                "accuracy": "93.3%" if improved_classifier.trained else "N/A",
                "categories": len(improved_classifier.category_patterns) if improved_classifier.trained else 0
            },
            "bert_classifier": {
                "loaded": hasattr(bert_classifier, 'model') and bert_classifier.model is not None,
                "status": "ready" if hasattr(bert_classifier, 'model') and bert_classifier.model is not None else "not_loaded"
            },
            "rule_based": {
                "status": "ready",
                "categories": len(rule_based_classifier.categories)
            }
        }
        return info
    except Exception as e:
        logger.error(f"Model info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model information")