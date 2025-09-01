from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import time
from datetime import datetime

from app.models.rule_based_classifier import rule_based_classifier
from app.models.improved_classifier import improved_classifier
from app.models.bert_classifier import bert_classifier
from app.models.sentiment_analyzer import sentiment_analyzer
from app.preprocessing.text_processor import text_processor
from app.analytics.trend_detector import trend_detector
from app.monitoring.model_monitor import model_monitor

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

class HealthResponse(BaseModel):
    status: str
    models: Dict[str, str]
    timestamp: str
    uptime: float

class TrendRequest(BaseModel):
    tickets: List[Dict[str, Any]] = Field(..., description="List of ticket data with timestamps")
    time_period: str = Field(default="daily", description="Time period for analysis")

class BERTTrainingRequest(BaseModel):
    training_data_path: str = Field(default="data/expanded_tickets.json", description="Path to training data")
    epochs: int = Field(default=3, description="Number of training epochs")
    batch_size: int = Field(default=16, description="Training batch size")
    learning_rate: float = Field(default=2e-5, description="Learning rate")

# Global variables for monitoring
start_time = time.time()
model_status = {
    "improved_classifier": "healthy",
    "rule_based_classifier": "healthy",
    "bert_classifier": "healthy",
    "sentiment_analyzer": "healthy",
    "text_processor": "healthy"
}

@router.post("/classify", response_model=TicketResponse)
async def classify_ticket(request: TicketRequest):
    """
    Classify a support ticket into categories using improved classifier
    """
    start_time_request = time.time()
    
    try:
        # Preprocess text
        processed_text = text_processor.preprocess(request.text)
        
        # Try improved classifier first
        try:
            classification_result = improved_classifier.classify_with_confidence_label(processed_text)
            classifier_used = "improved"
            
            # Track prediction for monitoring
            model_monitor.track_prediction("improved_classifier", classification_result)
            
        except Exception as e:
            logger.warning(f"Improved classifier failed, falling back to rule-based: {e}")
            # Fallback to original classifier
            classification_result = rule_based_classifier.classify_with_confidence_label(processed_text)
            classifier_used = "rule_based"
            model_status["improved_classifier"] = "degraded"
            
            # Track prediction for monitoring
            model_monitor.track_prediction("rule_based_classifier", classification_result)
        
        processing_time = time.time() - start_time_request
        
        return TicketResponse(
            category=classification_result["category"],
            confidence=classification_result["confidence"],
            confidence_label=classification_result["confidence_label"],
            text=request.text,
            processing_time=processing_time,
            classifier_used=classifier_used
        )
        
    except Exception as e:
        logger.error(f"Error in ticket classification: {e}")
        model_status["improved_classifier"] = "error"
        model_status["rule_based_classifier"] = "error"
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@router.post("/classify/bert", response_model=TicketResponse)
async def classify_ticket_bert(request: TicketRequest):
    """
    Classify a support ticket using BERT model
    """
    start_time_request = time.time()
    
    try:
        # Check if BERT model is loaded
        if bert_classifier.model is None:
            raise HTTPException(status_code=503, detail="BERT model not loaded. Please train or load a model first.")
        
        # Preprocess text
        processed_text = text_processor.preprocess(request.text)
        
        # Use BERT classifier
        classification_result = bert_classifier.predict_with_confidence_label(processed_text)
        
        # Track prediction for monitoring
        model_monitor.track_prediction("bert_classifier", classification_result)
        
        processing_time = time.time() - start_time_request
        
        return TicketResponse(
            category=classification_result["category"],
            confidence=classification_result["confidence"],
            confidence_label=classification_result["confidence_label"],
            text=request.text,
            processing_time=processing_time,
            classifier_used="bert"
        )
        
    except Exception as e:
        logger.error(f"Error in BERT ticket classification: {e}")
        model_status["bert_classifier"] = "error"
        raise HTTPException(status_code=500, detail=f"BERT classification failed: {str(e)}")

@router.post("/classify/improved", response_model=TicketResponse)
async def classify_ticket_improved(request: TicketRequest):
    """
    Classify a support ticket using only the improved classifier
    """
    start_time_request = time.time()
    
    try:
        # Preprocess text
        processed_text = text_processor.preprocess(request.text)
        
        # Use improved classifier only
        classification_result = improved_classifier.classify_with_confidence_label(processed_text)
        
        # Track prediction for monitoring
        model_monitor.track_prediction("improved_classifier", classification_result)
        
        processing_time = time.time() - start_time_request
        
        return TicketResponse(
            category=classification_result["category"],
            confidence=classification_result["confidence"],
            confidence_label=classification_result["confidence_label"],
            text=request.text,
            processing_time=processing_time,
            classifier_used="improved"
        )
        
    except Exception as e:
        logger.error(f"Error in improved ticket classification: {e}")
        model_status["improved_classifier"] = "error"
        raise HTTPException(status_code=500, detail=f"Improved classification failed: {str(e)}")

@router.post("/classify/rule-based", response_model=TicketResponse)
async def classify_ticket_rule_based(request: TicketRequest):
    """
    Classify a support ticket using only the rule-based classifier
    """
    start_time_request = time.time()
    
    try:
        # Preprocess text
        processed_text = text_processor.preprocess(request.text)
        
        # Use rule-based classifier only
        classification_result = rule_based_classifier.classify_with_confidence_label(processed_text)
        
        # Track prediction for monitoring
        model_monitor.track_prediction("rule_based_classifier", classification_result)
        
        processing_time = time.time() - start_time_request
        
        return TicketResponse(
            category=classification_result["category"],
            confidence=classification_result["confidence"],
            confidence_label=classification_result["confidence_label"],
            text=request.text,
            processing_time=processing_time,
            classifier_used="rule_based"
        )
        
    except Exception as e:
        logger.error(f"Error in rule-based ticket classification: {e}")
        model_status["rule_based_classifier"] = "error"
        raise HTTPException(status_code=500, detail=f"Rule-based classification failed: {str(e)}")

@router.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    """
    Analyze sentiment of support ticket text
    """
    start_time_request = time.time()
    
    try:
        # Analyze sentiment
        sentiment_result = sentiment_analyzer.analyze_sentiment(request.text)
        
        processing_time = time.time() - start_time_request
        
        return SentimentResponse(
            sentiment=sentiment_result["sentiment"],
            sentiment_score=sentiment_result["sentiment_score"],
            confidence=sentiment_result["confidence"],
            confidence_label=sentiment_result["confidence_label"],
            text=request.text,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {e}")
        model_status["sentiment_analyzer"] = "error"
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")

@router.post("/batch", response_model=BatchResponse)
async def batch_process_tickets(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    Process multiple tickets for both classification and sentiment analysis
    """
    start_time_request = time.time()
    
    try:
        # Validate input
        if len(request.tickets) > 1000:
            raise HTTPException(status_code=400, detail="Maximum 1000 tickets allowed per batch")
        
        # Process tickets
        classifications = []
        sentiments = []
        
        for ticket_text in request.tickets:
            # Preprocess text
            processed_text = text_processor.preprocess(ticket_text)
            
            # Classify with improved classifier (with fallback)
            try:
                classification_result = improved_classifier.classify_with_confidence_label(processed_text)
                classification_result["classifier_used"] = "improved"
                model_monitor.track_prediction("improved_classifier", classification_result)
            except Exception as e:
                logger.warning(f"Improved classifier failed for batch, using rule-based: {e}")
                classification_result = rule_based_classifier.classify_with_confidence_label(processed_text)
                classification_result["classifier_used"] = "rule_based"
                model_monitor.track_prediction("rule_based_classifier", classification_result)
            
            classifications.append(classification_result)
            
            # Analyze sentiment
            sentiment_result = sentiment_analyzer.analyze_sentiment(ticket_text)
            sentiments.append(sentiment_result)
        
        processing_time = time.time() - start_time_request
        
        # Log batch processing metrics
        background_tasks.add_task(log_batch_metrics, len(request.tickets), processing_time)
        
        return BatchResponse(
            classifications=classifications,
            sentiments=sentiments,
            processing_time=processing_time,
            total_tickets=len(request.tickets)
        )
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

@router.post("/trends/volume")
async def calculate_volume_trends(request: TrendRequest):
    """
    Calculate volume trends for ticket categories
    """
    try:
        trends = trend_detector.calculate_volume_trends(request.tickets, request.time_period)
        return trends
    except Exception as e:
        logger.error(f"Error calculating volume trends: {e}")
        raise HTTPException(status_code=500, detail=f"Volume trend calculation failed: {str(e)}")

@router.post("/trends/sentiment")
async def calculate_sentiment_trends(request: TrendRequest):
    """
    Calculate sentiment trends over time
    """
    try:
        trends = trend_detector.calculate_sentiment_trends(request.tickets, request.time_period)
        return trends
    except Exception as e:
        logger.error(f"Error calculating sentiment trends: {e}")
        raise HTTPException(status_code=500, detail=f"Sentiment trend calculation failed: {str(e)}")

@router.post("/trends/anomalies")
async def detect_anomalies(request: TrendRequest):
    """
    Detect anomalies in ticket patterns
    """
    try:
        anomalies = trend_detector.detect_anomalies(request.tickets)
        return anomalies
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")

@router.post("/trends/alerts")
async def generate_trend_alerts(request: TrendRequest):
    """
    Generate alerts based on trend analysis
    """
    try:
        # Calculate trends first
        volume_trends = trend_detector.calculate_volume_trends(request.tickets, request.time_period)
        sentiment_trends = trend_detector.calculate_sentiment_trends(request.tickets, request.time_period)
        
        # Generate alerts
        volume_alerts = trend_detector.generate_alerts(volume_trends)
        sentiment_alerts = trend_detector.generate_alerts(sentiment_trends)
        
        return {
            "volume_alerts": volume_alerts,
            "sentiment_alerts": sentiment_alerts,
            "total_alerts": len(volume_alerts) + len(sentiment_alerts)
        }
    except Exception as e:
        logger.error(f"Error generating trend alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Alert generation failed: {str(e)}")

@router.get("/monitoring/health/{model_name}")
async def get_model_health(model_name: str):
    """
    Get health status for a specific model
    """
    try:
        health_data = model_monitor.get_model_health_dashboard(model_name)
        return health_data
    except Exception as e:
        logger.error(f"Error getting model health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/monitoring/health")
async def get_all_models_health():
    """
    Get health status for all monitored models
    """
    try:
        health_data = model_monitor.get_all_models_health()
        return health_data
    except Exception as e:
        logger.error(f"Error getting all models health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/monitoring/drift/{model_name}")
async def check_model_drift(model_name: str):
    """
    Check for model drift
    """
    try:
        drift_results = model_monitor.detect_model_drift(model_name)
        return drift_results
    except Exception as e:
        logger.error(f"Error checking model drift: {e}")
        raise HTTPException(status_code=500, detail=f"Drift detection failed: {str(e)}")

@router.get("/monitoring/retraining/{model_name}")
async def check_retraining_triggers(model_name: str):
    """
    Check if model retraining is needed
    """
    try:
        retraining_results = model_monitor.check_retraining_triggers(model_name)
        return retraining_results
    except Exception as e:
        logger.error(f"Error checking retraining triggers: {e}")
        raise HTTPException(status_code=500, detail=f"Retraining check failed: {str(e)}")

@router.post("/bert/train")
async def train_bert_model(request: BERTTrainingRequest):
    """
    Train/fine-tune BERT model on support ticket data
    """
    try:
        # Prepare data
        train_dataset, val_dataset = bert_classifier.prepare_data(request.training_data_path)
        
        # Fine-tune model
        model_path = bert_classifier.fine_tune(
            train_dataset, 
            val_dataset,
            epochs=request.epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate
        )
        
        # Load the trained model
        bert_classifier.load_model(model_path)
        
        return {
            "message": "BERT model training completed successfully",
            "model_path": model_path,
            "training_params": {
                "epochs": request.epochs,
                "batch_size": request.batch_size,
                "learning_rate": request.learning_rate
            }
        }
        
    except Exception as e:
        logger.error(f"Error training BERT model: {e}")
        raise HTTPException(status_code=500, detail=f"BERT training failed: {str(e)}")

@router.get("/bert/info")
async def get_bert_model_info():
    """
    Get information about the BERT model
    """
    try:
        model_info = bert_classifier.get_model_info()
        return model_info
    except Exception as e:
        logger.error(f"Error getting BERT model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get BERT model info: {str(e)}")

@router.post("/bert/evaluate")
async def evaluate_bert_model():
    """
    Evaluate BERT model performance
    """
    try:
        if bert_classifier.model is None:
            raise HTTPException(status_code=503, detail="BERT model not loaded")
        
        evaluation_results = bert_classifier.evaluate()
        return evaluation_results
        
    except Exception as e:
        logger.error(f"Error evaluating BERT model: {e}")
        raise HTTPException(status_code=500, detail=f"BERT evaluation failed: {str(e)}")

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check health status of ML models and API
    """
    try:
        # Test models with sample data
        test_text = "This is a test ticket for health check"
        
        # Test improved classification
        try:
            improved_classifier.classify(test_text)
            model_status["improved_classifier"] = "healthy"
        except Exception as e:
            logger.error(f"Improved classifier health check failed: {e}")
            model_status["improved_classifier"] = "error"
        
        # Test rule-based classification
        try:
            rule_based_classifier.classify(test_text)
            model_status["rule_based_classifier"] = "healthy"
        except Exception as e:
            logger.error(f"Rule-based classifier health check failed: {e}")
            model_status["rule_based_classifier"] = "error"
        
        # Test BERT classification
        try:
            if bert_classifier.model is not None:
                bert_classifier.predict(test_text)
                model_status["bert_classifier"] = "healthy"
            else:
                model_status["bert_classifier"] = "not_loaded"
        except Exception as e:
            logger.error(f"BERT classifier health check failed: {e}")
            model_status["bert_classifier"] = "error"
        
        # Test sentiment analysis
        try:
            sentiment_analyzer.analyze_sentiment(test_text)
            model_status["sentiment_analyzer"] = "healthy"
        except Exception as e:
            logger.error(f"Sentiment model health check failed: {e}")
            model_status["sentiment_analyzer"] = "error"
        
        # Test text preprocessing
        try:
            text_processor.preprocess(test_text)
            model_status["text_processor"] = "healthy"
        except Exception as e:
            logger.error(f"Text processor health check failed: {e}")
            model_status["text_processor"] = "error"
        
        # Determine overall status
        overall_status = "healthy" if all(status == "healthy" for status in model_status.values()) else "degraded"
        
        uptime = time.time() - start_time
        
        return HealthResponse(
            status=overall_status,
            models=model_status,
            timestamp=datetime.now().isoformat(),
            uptime=uptime
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/categories")
async def get_supported_categories():
    """
    Get list of supported ticket categories
    """
    try:
        categories = improved_classifier.get_supported_categories()
        return {
            "categories": categories,
            "total_categories": len(categories)
        }
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@router.get("/classifier/stats")
async def get_classifier_stats():
    """
    Get statistics about the improved classifier
    """
    try:
        training_stats = improved_classifier.get_training_stats()
        return {
            "training_stats": training_stats,
            "classifier_type": "improved",
            "accuracy_estimate": "93.3% (based on test data)"
        }
    except Exception as e:
        logger.error(f"Error getting classifier stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get classifier stats: {str(e)}")

@router.post("/trends")
async def calculate_trends(request: BatchRequest):
    """
    Calculate trends from batch sentiment analysis
    """
    try:
        # Analyze sentiments for all tickets
        sentiment_results = sentiment_analyzer.batch_analyze_sentiment(request.tickets)
        
        # Calculate trends
        trends = sentiment_analyzer.calculate_sentiment_trends(sentiment_results)
        
        # Detect anomalies
        anomalies = sentiment_analyzer.detect_sentiment_anomalies(sentiment_results)
        
        return {
            "trends": trends,
            "anomalies": anomalies,
            "total_tickets": len(request.tickets)
        }
        
    except Exception as e:
        logger.error(f"Error calculating trends: {e}")
        raise HTTPException(status_code=500, detail=f"Trend calculation failed: {str(e)}")

def log_batch_metrics(total_tickets: int, processing_time: float):
    """Log batch processing metrics for monitoring"""
    logger.info(f"Batch processed {total_tickets} tickets in {processing_time:.2f}s "
                f"({total_tickets/processing_time:.1f} tickets/sec)") 