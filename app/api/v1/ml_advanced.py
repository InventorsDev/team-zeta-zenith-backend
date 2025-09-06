from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import time

from app.ml import (
    similarity_detector,
    trend_detector, 
    ticket_forecaster,
    model_monitor
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models
class SimilarityRequest(BaseModel):
    text: str = Field(..., description="Text to find similar tickets for")
    threshold: float = Field(0.7, description="Similarity threshold", ge=0.0, le=1.0)
    top_k: int = Field(5, description="Number of similar tickets to return", ge=1, le=20)

class ClusteringRequest(BaseModel):
    tickets: List[str] = Field(..., description="List of tickets to cluster", min_items=2, max_items=1000)
    num_clusters: Optional[int] = Field(None, description="Number of clusters (auto-detect if not specified)")

class TrendRequest(BaseModel):
    tickets: List[Dict[str, Any]] = Field(..., description="List of tickets with timestamps and categories")
    days: int = Field(30, description="Number of days to analyze", ge=1, le=365)

class ForecastRequest(BaseModel):
    historical_data: List[Dict[str, Any]] = Field(..., description="Historical ticket data")
    forecast_days: int = Field(7, description="Days to forecast ahead", ge=1, le=90)

# Similarity and clustering endpoints
@router.post("/similarity")
async def find_similar_tickets(request: SimilarityRequest):
    """Find tickets similar to the given text"""
    try:
        start_time = time.time()
        
        similar_tickets = similarity_detector.find_similar(
            request.text, 
            threshold=request.threshold,
            top_k=request.top_k
        )
        
        processing_time = time.time() - start_time
        
        return {
            "query_text": request.text,
            "similar_tickets": similar_tickets,
            "threshold": request.threshold,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Similarity detection error: {e}")
        raise HTTPException(status_code=500, detail="Similarity detection failed")

@router.post("/clustering")
async def cluster_tickets(request: ClusteringRequest):
    """Cluster similar tickets together"""
    try:
        start_time = time.time()
        
        clusters = similarity_detector.cluster_tickets(
            request.tickets,
            num_clusters=request.num_clusters
        )
        
        processing_time = time.time() - start_time
        
        return {
            "clusters": clusters,
            "total_tickets": len(request.tickets),
            "num_clusters": len(clusters),
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        raise HTTPException(status_code=500, detail="Clustering failed")

@router.post("/duplicates")
async def detect_duplicates(request: SimilarityRequest):
    """Detect potential duplicate tickets"""
    try:
        start_time = time.time()
        
        duplicates = similarity_detector.detect_duplicates(
            request.text,
            threshold=request.threshold
        )
        
        processing_time = time.time() - start_time
        
        return {
            "query_text": request.text,
            "potential_duplicates": duplicates,
            "threshold": request.threshold,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Duplicate detection error: {e}")
        raise HTTPException(status_code=500, detail="Duplicate detection failed")

@router.post("/recommendations")
async def get_recommendations(request: SimilarityRequest):
    """Get recommendations for similar past tickets"""
    try:
        start_time = time.time()
        
        recommendations = similarity_detector.recommend_solutions(
            request.text,
            top_k=request.top_k
        )
        
        processing_time = time.time() - start_time
        
        return {
            "query_text": request.text,
            "recommendations": recommendations,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        raise HTTPException(status_code=500, detail="Recommendation failed")

# Trend analysis endpoints
@router.post("/trends/volume")
async def analyze_volume_trends(request: TrendRequest):
    """Analyze ticket volume trends"""
    try:
        start_time = time.time()
        
        trends = trend_detector.analyze_volume_trends(
            request.tickets,
            days=request.days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "volume_trends": trends,
            "analysis_period_days": request.days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Volume trend analysis error: {e}")
        raise HTTPException(status_code=500, detail="Volume trend analysis failed")

@router.post("/trends/sentiment")
async def analyze_sentiment_trends(request: TrendRequest):
    """Analyze sentiment trends over time"""
    try:
        start_time = time.time()
        
        trends = trend_detector.analyze_sentiment_trends(
            request.tickets,
            days=request.days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "sentiment_trends": trends,
            "analysis_period_days": request.days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Sentiment trend analysis error: {e}")
        raise HTTPException(status_code=500, detail="Sentiment trend analysis failed")

@router.post("/trends/anomalies")
async def detect_anomalies(request: TrendRequest):
    """Detect anomalies in ticket patterns"""
    try:
        start_time = time.time()
        
        anomalies = trend_detector.detect_anomalies(
            request.tickets,
            days=request.days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "anomalies": anomalies,
            "analysis_period_days": request.days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        raise HTTPException(status_code=500, detail="Anomaly detection failed")

# Forecasting endpoints
@router.post("/forecast/volume")
async def forecast_ticket_volume(request: ForecastRequest):
    """Forecast ticket volume for the next period"""
    try:
        start_time = time.time()
        
        forecast = ticket_forecaster.forecast_volume(
            request.historical_data,
            forecast_days=request.forecast_days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "volume_forecast": forecast,
            "forecast_days": request.forecast_days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Volume forecasting error: {e}")
        raise HTTPException(status_code=500, detail="Volume forecasting failed")

@router.post("/forecast/category")
async def forecast_category_trends(request: ForecastRequest):
    """Forecast trends by category"""
    try:
        start_time = time.time()
        
        forecast = ticket_forecaster.forecast_category_trends(
            request.historical_data,
            forecast_days=request.forecast_days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "category_forecast": forecast,
            "forecast_days": request.forecast_days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Category forecasting error: {e}")
        raise HTTPException(status_code=500, detail="Category forecasting failed")

@router.post("/forecast/scenarios")
async def forecast_scenarios(request: ForecastRequest):
    """Generate what-if forecast scenarios"""
    try:
        start_time = time.time()
        
        scenarios = ticket_forecaster.generate_scenarios(
            request.historical_data,
            forecast_days=request.forecast_days
        )
        
        processing_time = time.time() - start_time
        
        return {
            "scenarios": scenarios,
            "forecast_days": request.forecast_days,
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Scenario forecasting error: {e}")
        raise HTTPException(status_code=500, detail="Scenario forecasting failed")

# Monitoring endpoints
@router.get("/monitoring/health")
async def model_health_dashboard():
    """Get comprehensive model health dashboard"""
    try:
        health_data = model_monitor.get_health_dashboard()
        return health_data
    
    except Exception as e:
        logger.error(f"Model health monitoring error: {e}")
        raise HTTPException(status_code=500, detail="Model health monitoring failed")

@router.get("/monitoring/drift/{model_name}")
async def check_model_drift(model_name: str):
    """Check for model drift in a specific model"""
    try:
        drift_data = model_monitor.check_drift(model_name)
        return drift_data
    
    except Exception as e:
        logger.error(f"Model drift check error: {e}")
        raise HTTPException(status_code=500, detail="Model drift check failed")

@router.get("/monitoring/performance/{model_name}")
async def get_model_performance(model_name: str):
    """Get performance metrics for a specific model"""
    try:
        performance = model_monitor.get_performance_metrics(model_name)
        return performance
    
    except Exception as e:
        logger.error(f"Model performance retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Model performance retrieval failed")

# Optimization endpoints
@router.post("/optimize/benchmark")
async def benchmark_performance():
    """Benchmark ML system performance"""
    try:
        start_time = time.time()
        
        benchmark_results = {
            "single_classification_time": 0.0,
            "batch_processing_time": 0.0,
            "sentiment_analysis_time": 0.0,
            "similarity_detection_time": 0.0
        }
        
        # Sample benchmark tests
        test_text = "This is a sample support ticket for testing performance"
        
        # Single classification benchmark
        from app.ml.models.improved_classifier import improved_classifier
        if improved_classifier.trained:
            class_start = time.time()
            improved_classifier.classify(test_text)
            benchmark_results["single_classification_time"] = time.time() - class_start
        
        # Sentiment analysis benchmark
        from app.ml.models.sentiment_analyzer import sentiment_analyzer
        sent_start = time.time()
        sentiment_analyzer.analyze_sentiment(test_text)
        benchmark_results["sentiment_analysis_time"] = time.time() - sent_start
        
        total_time = time.time() - start_time
        
        return {
            "benchmark_results": benchmark_results,
            "total_benchmark_time": total_time,
            "timestamp": time.time()
        }
    
    except Exception as e:
        logger.error(f"Performance benchmark error: {e}")
        raise HTTPException(status_code=500, detail="Performance benchmark failed")