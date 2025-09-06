"""
Internal ML Service Layer
This provides ML functionality to business endpoints without exposing ML APIs publicly
"""
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from app.ml import (
    rule_based_classifier,
    improved_classifier,
    sentiment_analyzer,
    text_processor,
    similarity_detector,
    trend_detector,
    ticket_forecaster,
    model_monitor
)

logger = logging.getLogger(__name__)

class MLService:
    """Internal ML service for use by business endpoints"""
    
    def __init__(self):
        self.is_available = self._check_availability()
        logger.info(f"ML Service initialized. Available: {self.is_available}")
    
    def _check_availability(self) -> bool:
        """Check if ML components are available"""
        try:
            # Check if at least basic ML components are available
            return (rule_based_classifier is not None or 
                   improved_classifier is not None or
                   sentiment_analyzer is not None)
        except Exception as e:
            logger.error(f"ML availability check failed: {e}")
            return False
    
    def classify_ticket(self, text: str) -> Dict[str, Any]:
        """
        Classify a support ticket
        Returns: {category, confidence, confidence_label, processing_time}
        """
        if not self.is_available:
            return self._get_fallback_classification(text)
        
        start_time = time.time()
        
        try:
            # Clean the input text
            clean_text = text_processor.clean_text(text) if text_processor else text
            
            # Try improved classifier first (highest accuracy)
            if improved_classifier and improved_classifier.trained:
                category, confidence = improved_classifier.classify(clean_text)
                classifier_used = "improved"
            elif rule_based_classifier:
                category, confidence = rule_based_classifier.classify(clean_text)
                classifier_used = "rule_based"
            else:
                return self._get_fallback_classification(text)
            
            # Determine confidence label
            confidence_label = self._get_confidence_label(confidence)
            processing_time = time.time() - start_time
            
            return {
                "category": category,
                "confidence": confidence,
                "confidence_label": confidence_label,
                "processing_time": processing_time,
                "classifier_used": classifier_used
            }
        
        except Exception as e:
            logger.error(f"Ticket classification failed: {e}")
            return self._get_fallback_classification(text)
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text
        Returns: {sentiment, sentiment_score, confidence, processing_time}
        """
        if not self.is_available or not sentiment_analyzer:
            return self._get_fallback_sentiment(text)
        
        start_time = time.time()
        
        try:
            clean_text = text_processor.clean_text(text) if text_processor else text
            sentiment, score, confidence = sentiment_analyzer.analyze_sentiment(clean_text)
            
            processing_time = time.time() - start_time
            
            return {
                "sentiment": sentiment,
                "sentiment_score": score,
                "confidence": confidence,
                "confidence_label": self._get_confidence_label(confidence),
                "processing_time": processing_time
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return self._get_fallback_sentiment(text)
    
    def find_similar_tickets(self, text: str, threshold: float = 0.7, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find tickets similar to the given text
        Returns: List of similar tickets with similarity scores
        """
        if not similarity_detector:
            logger.warning("Similarity detector not available")
            return []
        
        try:
            similar_tickets = similarity_detector.find_similar(text, threshold=threshold, top_k=top_k)
            return similar_tickets
        except Exception as e:
            logger.error(f"Similarity detection failed: {e}")
            return []
    
    def detect_duplicates(self, text: str, threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate tickets
        Returns: List of potential duplicates
        """
        if not similarity_detector:
            logger.warning("Similarity detector not available for duplicate detection")
            return []
        
        try:
            duplicates = similarity_detector.detect_duplicates(text, threshold=threshold)
            return duplicates
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            return []
    
    def analyze_ticket_trends(self, tickets: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
        """
        Analyze trends in ticket data
        Returns: Trend analysis results
        """
        if not trend_detector:
            logger.warning("Trend detector not available")
            return {"trends": [], "analysis_period_days": days}
        
        try:
            trends = trend_detector.analyze_volume_trends(tickets, days=days)
            return {"trends": trends, "analysis_period_days": days}
        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            return {"trends": [], "analysis_period_days": days, "error": str(e)}
    
    def get_ticket_analytics(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate comprehensive analytics for a set of tickets
        Returns: Analytics including categories, sentiments, trends
        """
        analytics = {
            "total_tickets": len(tickets),
            "categories": {},
            "sentiments": {},
            "processing_time": 0
        }
        
        start_time = time.time()
        
        try:
            # Analyze each ticket
            for ticket in tickets:
                text = ticket.get('content', ticket.get('description', ''))
                if not text:
                    continue
                
                # Classification
                classification = self.classify_ticket(text)
                category = classification.get('category', 'unknown')
                analytics['categories'][category] = analytics['categories'].get(category, 0) + 1
                
                # Sentiment analysis
                sentiment_result = self.analyze_sentiment(text)
                sentiment = sentiment_result.get('sentiment', 'neutral')
                analytics['sentiments'][sentiment] = analytics['sentiments'].get(sentiment, 0) + 1
            
            # Calculate percentages
            total = analytics['total_tickets']
            if total > 0:
                analytics['categories_percentage'] = {
                    cat: round((count / total) * 100, 1) 
                    for cat, count in analytics['categories'].items()
                }
                analytics['sentiments_percentage'] = {
                    sent: round((count / total) * 100, 1) 
                    for sent, count in analytics['sentiments'].items()
                }
            
            analytics['processing_time'] = time.time() - start_time
            
        except Exception as e:
            logger.error(f"Ticket analytics generation failed: {e}")
            analytics['error'] = str(e)
        
        return analytics
    
    def enhance_ticket_data(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance ticket data with ML insights
        This is called automatically when tickets are created/updated
        """
        enhanced_data = ticket_data.copy()
        text = ticket_data.get('description', ticket_data.get('content', ''))
        
        # Always add ML fields, even if ML is not fully available
        try:
            # Add classification
            classification = self.classify_ticket(text)
            enhanced_data['ml_category'] = classification.get('category')
            enhanced_data['ml_confidence'] = classification.get('confidence')
            enhanced_data['ml_confidence_label'] = classification.get('confidence_label')
            
            # Add sentiment
            sentiment = self.analyze_sentiment(text)
            enhanced_data['ml_sentiment'] = sentiment.get('sentiment')
            enhanced_data['ml_sentiment_score'] = sentiment.get('sentiment_score')
            
            # Add processing info
            enhanced_data['ml_processed_at'] = datetime.utcnow().isoformat()
            enhanced_data['ml_available'] = self.is_available
            
            # Try to check for duplicates if similarity detector is available
            if similarity_detector:
                try:
                    duplicates = self.detect_duplicates(text)
                    if duplicates:
                        enhanced_data['potential_duplicates'] = len(duplicates)
                        enhanced_data['similar_tickets'] = duplicates[:3]  # Top 3
                except Exception:
                    # Silent fail for duplicates - not critical
                    pass
            
        except Exception as e:
            logger.error(f"Ticket enhancement failed: {e}")
            # Still add basic ML fields even on error
            enhanced_data['ml_category'] = 'general'
            enhanced_data['ml_confidence'] = 0.5
            enhanced_data['ml_confidence_label'] = 'medium'
            enhanced_data['ml_sentiment'] = 'neutral'
            enhanced_data['ml_sentiment_score'] = 0.0
            enhanced_data['ml_available'] = False
            enhanced_data['ml_error'] = str(e)
        
        return enhanced_data
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get ML system health status"""
        status = {
            "available": self.is_available,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "improved_classifier": improved_classifier is not None and (
                    improved_classifier.trained if hasattr(improved_classifier, 'trained') else True
                ),
                "rule_based_classifier": rule_based_classifier is not None,
                "sentiment_analyzer": sentiment_analyzer is not None,
                "text_processor": text_processor is not None,
                "similarity_detector": similarity_detector is not None,
                "trend_detector": trend_detector is not None
            }
        }
        
        # Add model monitor data if available
        if model_monitor:
            try:
                health_data = model_monitor.get_health_dashboard()
                status['model_health'] = health_data
            except Exception as e:
                logger.warning(f"Model monitor health check failed: {e}")
        
        return status
    
    def _get_confidence_label(self, confidence: float) -> str:
        """Convert confidence score to label"""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _get_fallback_classification(self, text: str = "") -> Dict[str, Any]:
        """Fallback classification when ML is unavailable - with basic text analysis"""
        category = "general"
        confidence = 0.5
        
        if text:
            text_lower = text.lower()
            
            # Define keyword patterns with scores
            patterns = {
                "authentication": {
                    "keywords": ['login', 'password', 'signin', 'sign in', 'access', 'authentication', 'account', 'unlock', 'locked', 'forgot password', 'reset password', '2fa', 'verification', 'authorize'],
                    "confidence": 0.8
                },
                "billing": {
                    "keywords": ['bill', 'billing', 'charge', 'payment', 'invoice', 'subscription', 'refund', 'credit', 'debit', 'pricing', 'cost', 'fee', 'money', 'paid', 'upgrade', 'downgrade'],
                    "confidence": 0.8
                },
                "technical": {
                    "keywords": ['bug', 'error', 'crash', 'broken', 'not working', 'issue', 'problem', 'fail', 'failure', '500', '404', 'timeout', 'slow', 'performance', 'server', 'database', 'api'],
                    "confidence": 0.7
                },
                "support": {
                    "keywords": ['how', 'help', 'support', 'question', 'guide', 'tutorial', 'documentation', 'explain', 'understand', 'confused', 'setup', 'configure'],
                    "confidence": 0.6
                },
                "feature_request": {
                    "keywords": ['feature', 'request', 'suggestion', 'improvement', 'enhancement', 'new', 'add', 'would like', 'wish', 'hope', 'can you', 'possible'],
                    "confidence": 0.6
                }
            }
            
            # Score each category
            category_scores = {}
            for cat, data in patterns.items():
                score = 0
                for keyword in data["keywords"]:
                    if keyword in text_lower:
                        score += 1
                        # Boost score for exact phrase matches
                        if len(keyword.split()) > 1:
                            score += 0.5
                
                if score > 0:
                    category_scores[cat] = {
                        "score": score,
                        "confidence": min(data["confidence"] + (score - 1) * 0.1, 0.9)
                    }
            
            # Select best category
            if category_scores:
                best_category = max(category_scores.keys(), key=lambda k: category_scores[k]["score"])
                category = best_category
                confidence = category_scores[best_category]["confidence"]
        
        return {
            "category": category,
            "confidence": confidence,
            "confidence_label": self._get_confidence_label(confidence),
            "processing_time": 0.001,
            "classifier_used": "fallback"
        }
    
    def _get_fallback_sentiment(self, text: str = "") -> Dict[str, Any]:
        """Fallback sentiment when ML is unavailable - with basic text analysis"""
        sentiment = "neutral"
        score = 0.0
        confidence = 0.5
        
        if text:
            text_lower = text.lower()
            words = text_lower.split()
            
            # Enhanced sentiment word lists
            positive_words = [
                'love', 'great', 'awesome', 'excellent', 'fantastic', 'amazing', 'perfect', 
                'thank', 'thanks', 'good', 'nice', 'happy', 'satisfied', 'pleased', 'wonderful',
                'brilliant', 'outstanding', 'superb', 'magnificent', 'incredible', 'appreciate',
                'grateful', 'delighted', 'thrilled', 'excited', 'joy', 'best', 'better', 'impressive'
            ]
            
            negative_words = [
                'hate', 'terrible', 'awful', 'horrible', 'bad', 'worst', 'angry', 'frustrated', 
                'disappointed', 'annoying', 'broken', 'useless', 'stupid', 'crash', 'error', 
                'problem', 'issue', 'urgent', 'immediately', 'disgusting', 'pathetic', 'ridiculous',
                'outrageous', 'unacceptable', 'fail', 'failure', 'disaster', 'nightmare', 'mess',
                'sucks', 'rubbish', 'garbage', 'waste', 'hopeless', 'incompetent'
            ]
            
            # Intensifiers that modify sentiment strength
            intensifiers = ['very', 'extremely', 'incredibly', 'absolutely', 'totally', 'completely', 'really', 'so', 'quite']
            
            # Count sentiment words with context
            positive_score = 0
            negative_score = 0
            
            for i, word in enumerate(words):
                # Check for intensifier before sentiment word
                multiplier = 1.5 if i > 0 and words[i-1] in intensifiers else 1.0
                
                if word in positive_words:
                    positive_score += multiplier
                elif word in negative_words:
                    negative_score += multiplier
            
            # Calculate total words for normalization
            total_words = len(words)
            if total_words > 0:
                positive_ratio = positive_score / total_words
                negative_ratio = negative_score / total_words
                
                # Determine sentiment based on ratios
                if positive_ratio > negative_ratio and positive_score > 0:
                    sentiment = "positive"
                    score = min(0.9, 0.2 + positive_ratio * 2)
                    confidence = min(0.8, 0.5 + positive_ratio)
                elif negative_ratio > positive_ratio and negative_score > 0:
                    sentiment = "negative"  
                    score = max(-0.9, -0.2 - negative_ratio * 2)
                    confidence = min(0.8, 0.5 + negative_ratio)
            
            # Look for urgency indicators (usually negative context)
            urgency_words = ['urgent', 'emergency', 'immediately', 'asap', 'critical', 'serious', 'help!', 'please help']
            urgency_count = sum(1 for word in urgency_words if word in text_lower)
            
            if urgency_count > 0:
                if sentiment == "neutral":
                    sentiment = "negative"
                    score = -0.4
                    confidence = 0.7
                elif sentiment == "negative":
                    score = max(score - 0.3, -0.9)
                    confidence = min(confidence + 0.1, 0.9)
            
            # Look for gratitude patterns (positive indicators)
            gratitude_patterns = ['thank you', 'thanks for', 'appreciate', 'grateful']
            if any(pattern in text_lower for pattern in gratitude_patterns):
                if sentiment == "neutral":
                    sentiment = "positive"
                    score = 0.4
                    confidence = 0.7
                elif sentiment == "positive":
                    score = min(score + 0.2, 0.9)
                    confidence = min(confidence + 0.1, 0.9)
        
        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "confidence": confidence,
            "confidence_label": self._get_confidence_label(confidence),
            "processing_time": 0.001
        }

# Create singleton instance
ml_service = MLService()