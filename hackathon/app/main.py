from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Routers
from app.api.ml_endpoints import router as ml_router
from app.api.ml_sprint3_endpoints import router as ml_sprint3_router

# Logging
from app.utils.logging import setup_logging

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Support Ticket Analysis ML System",
    description="ML-powered support ticket classification, sentiment analysis, trend detection, monitoring, and advanced analytics",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include ML API routes
app.include_router(ml_router, prefix="/api/v1/ml", tags=["ML Core"])
app.include_router(ml_sprint3_router, prefix="/api/v1/ml/sprint3", tags=["ML Advanced"])

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "message": "Support Ticket Analysis ML System v3.0 - Sprint 3",
        "version": "3.0.0",
        "status": "running",
        "accuracy": "93.3% (improved classifier) + BERT",
        "sprint": "Sprint 3 - Advanced Analytics & Slack Integration",
        "endpoints": {
            # Core endpoints (Sprint 1 & 2)
            "classification": "/api/v1/ml/classify",
            "classification_improved": "/api/v1/ml/classify/improved",
            "classification_rule_based": "/api/v1/ml/classify/rule-based",
            "classification_bert": "/api/v1/ml/classify/bert",
            "sentiment": "/api/v1/ml/sentiment",
            "batch": "/api/v1/ml/batch",
            "health": "/api/v1/ml/health",
            "categories": "/api/v1/ml/categories",
            "classifier_stats": "/api/v1/ml/classifier/stats",
            "trends": "/api/v1/ml/trends",
            "volume_trends": "/api/v1/ml/trends/volume",
            "sentiment_trends": "/api/v1/ml/trends/sentiment",
            "anomalies": "/api/v1/ml/trends/anomalies",
            "alerts": "/api/v1/ml/trends/alerts",
            "model_health": "/api/v1/ml/monitoring/health",
            "model_drift": "/api/v1/ml/monitoring/drift/{model_name}",
            "retraining_check": "/api/v1/ml/monitoring/retraining/{model_name}",
            "bert_train": "/api/v1/ml/bert/train",
            "bert_info": "/api/v1/ml/bert/info",
            "bert_evaluate": "/api/v1/ml/bert/evaluate",

            # Sprint 3 endpoints
            "similarity": "/api/v1/ml/sprint3/similarity",
            "clustering": "/api/v1/ml/sprint3/clustering",
            "duplicates": "/api/v1/ml/sprint3/duplicates",
            "recommendations": "/api/v1/ml/sprint3/recommendations",
            "forecast_volume": "/api/v1/ml/sprint3/forecast/volume",
            "forecast_category": "/api/v1/ml/sprint3/forecast/category",
            "forecast_scenarios": "/api/v1/ml/sprint3/forecast/scenarios",
            "optimize_benchmark": "/api/v1/ml/sprint3/optimize/benchmark"
        },
        "features": {
            "improved_classifier": "93.3% accuracy with learned patterns",
            "bert_classifier": "BERT-based classification with fine-tuning",
            "sentiment_analysis": "VADER-based sentiment scoring",
            "trend_detection": "Volume and sentiment trend analysis",
            "anomaly_detection": "Pattern anomaly detection",
            "model_monitoring": "Performance tracking and drift detection",
            "automated_retraining": "Retraining triggers and alerts",
            "batch_processing": "Process multiple tickets efficiently",
            "health_monitoring": "Real-time model health checks",
            "fallback_system": "Automatic fallback to rule-based classifier",
            "similarity_detection": "Find related tickets with embeddings",
            "clustering": "Group similar tickets automatically",
            "duplicate_detection": "Detect repeated tickets",
            "recommendations": "Recommend similar past tickets",
            "forecasting": "Predict ticket volume and trends",
            "optimization": "Fast, memory-efficient inference for production"
        },
        "sprint_3_features": {
            "similarity_detection": "Text similarity & duplicate detection",
            "clustering": "Clustering of related tickets",
            "recommendations": "Similar ticket suggestions",
            "forecasting": "Ticket volume, category trends, seasonal patterns",
            "scenarios": "What-if prediction analysis",
            "optimization": "Inference <100ms, batch processing 1000+ tickets"
        }
    }

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "service": "support-ticket-ml-v3-sprint3"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
