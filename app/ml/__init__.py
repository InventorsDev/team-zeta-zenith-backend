"""
ML module initialization and component instantiation
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Create data and models directories if they don't exist
Path("data").mkdir(exist_ok=True)
Path("models").mkdir(exist_ok=True)

# Initialize ML components
try:
    from app.ml.models.rule_based_classifier import RuleBasedClassifier
    from app.ml.models.improved_classifier import ImprovedClassifier
    from app.ml.models.sentiment_analyzer import SentimentAnalyzer
    from app.ml.preprocessing.text_processor import TextProcessor
    
    # Initialize instances
    rule_based_classifier = RuleBasedClassifier()
    improved_classifier = ImprovedClassifier()
    sentiment_analyzer = SentimentAnalyzer()
    text_processor = TextProcessor()
    
    logger.info("ML components initialized successfully")
    
    # Try to initialize optional components that might need additional dependencies
    try:
        from app.ml.models.bert_classifier import BertClassifier
        bert_classifier = BertClassifier()
        logger.info("BERT classifier initialized")
    except Exception as e:
        logger.warning(f"BERT classifier initialization failed: {e}")
        bert_classifier = None
    
    try:
        from app.ml.analytics.trend_detector import TrendDetector
        from app.ml.analytics.similarity_detector import SimilarityDetector
        from app.ml.analytics.ticket_forecaster import TicketForecaster
        
        trend_detector = TrendDetector()
        similarity_detector = SimilarityDetector()
        ticket_forecaster = TicketForecaster()
        logger.info("Analytics components initialized")
    except Exception as e:
        logger.warning(f"Analytics components initialization failed: {e}")
        trend_detector = None
        similarity_detector = None
        ticket_forecaster = None
    
    try:
        from app.ml.monitoring.model_monitor import ModelMonitor
        model_monitor = ModelMonitor()
        logger.info("Model monitor initialized")
    except Exception as e:
        logger.warning(f"Model monitor initialization failed: {e}")
        model_monitor = None
        
except Exception as e:
    logger.error(f"Failed to initialize core ML components: {e}")
    # Create dummy components to prevent import errors
    rule_based_classifier = None
    improved_classifier = None
    sentiment_analyzer = None
    text_processor = None
    bert_classifier = None
    trend_detector = None
    similarity_detector = None
    ticket_forecaster = None
    model_monitor = None