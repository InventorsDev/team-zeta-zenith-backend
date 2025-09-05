from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Sentiment analysis for support tickets using VADER
    Returns sentiment score (-1 to +1) and confidence
    """
    
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        
        # Sentiment thresholds
        self.positive_threshold = 0.05
        self.negative_threshold = -0.05
        
        # Confidence thresholds
        self.high_confidence_threshold = 0.3
        self.medium_confidence_threshold = 0.15
    
    def _calculate_confidence(self, compound_score: float) -> float:
        """
        Calculate confidence based on compound score magnitude
        
        Args:
            compound_score: VADER compound score
            
        Returns:
            Confidence score (0 to 1)
        """
        # Higher absolute values indicate higher confidence
        confidence = min(abs(compound_score), 1.0)
        
        # Boost confidence for very strong sentiments
        if abs(compound_score) > 0.5:
            confidence = min(confidence * 1.2, 1.0)
        
        return confidence
    
    def _get_sentiment_label(self, compound_score: float) -> str:
        """
        Get sentiment label based on compound score
        
        Args:
            compound_score: VADER compound score
            
        Returns:
            Sentiment label
        """
        if compound_score >= self.positive_threshold:
            return "positive"
        elif compound_score <= self.negative_threshold:
            return "negative"
        else:
            return "neutral"
    
    def _get_confidence_label(self, confidence: float) -> str:
        """
        Get confidence label
        
        Args:
            confidence: Confidence score
            
        Returns:
            Confidence label
        """
        if confidence >= self.high_confidence_threshold:
            return "high"
        elif confidence >= self.medium_confidence_threshold:
            return "medium"
        else:
            return "low"
    
    def analyze_sentiment(self, text: str) -> Dict[str, any]:
        """
        Analyze sentiment of a single text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        if not text or not isinstance(text, str):
            return {
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "confidence_label": "low",
                "text": text,
                "vader_scores": {
                    "pos": 0.0,
                    "neg": 0.0,
                    "neu": 1.0,
                    "compound": 0.0
                }
            }
        
        try:
            # Get VADER sentiment scores
            vader_scores = self.analyzer.polarity_scores(text)
            compound_score = vader_scores['compound']
            
            # Calculate confidence
            confidence = self._calculate_confidence(compound_score)
            
            # Get labels
            sentiment_label = self._get_sentiment_label(compound_score)
            confidence_label = self._get_confidence_label(confidence)
            
            return {
                "sentiment": sentiment_label,
                "sentiment_score": compound_score,
                "confidence": confidence,
                "confidence_label": confidence_label,
                "text": text,
                "vader_scores": vader_scores
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "confidence_label": "low",
                "text": text,
                "vader_scores": {
                    "pos": 0.0,
                    "neg": 0.0,
                    "neu": 1.0,
                    "compound": 0.0
                }
            }
    
    def batch_analyze_sentiment(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Analyze sentiment of multiple texts
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of sentiment analysis results
        """
        return [self.analyze_sentiment(text) for text in texts]
    
    def calculate_sentiment_trends(self, sentiment_results: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Calculate sentiment trends from batch results
        
        Args:
            sentiment_results: List of sentiment analysis results
            
        Returns:
            Dictionary with trend analysis
        """
        if not sentiment_results:
            return {
                "total_tickets": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "average_sentiment": 0.0,
                "sentiment_distribution": {},
                "confidence_distribution": {}
            }
        
        # Extract sentiment scores and labels
        sentiment_scores = [result['sentiment_score'] for result in sentiment_results]
        sentiment_labels = [result['sentiment'] for result in sentiment_results]
        confidence_scores = [result['confidence'] for result in sentiment_results]
        
        # Calculate counts
        positive_count = sentiment_labels.count('positive')
        negative_count = sentiment_labels.count('negative')
        neutral_count = sentiment_labels.count('neutral')
        
        # Calculate averages
        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0.0
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        
        # Calculate distributions
        sentiment_distribution = {
            'positive': positive_count / len(sentiment_results),
            'negative': negative_count / len(sentiment_results),
            'neutral': neutral_count / len(sentiment_results)
        }
        
        # Confidence distribution
        high_conf = sum(1 for conf in confidence_scores if conf >= self.high_confidence_threshold)
        medium_conf = sum(1 for conf in confidence_scores if self.medium_confidence_threshold <= conf < self.high_confidence_threshold)
        low_conf = sum(1 for conf in confidence_scores if conf < self.medium_confidence_threshold)
        
        confidence_distribution = {
            'high': high_conf / len(sentiment_results),
            'medium': medium_conf / len(sentiment_results),
            'low': low_conf / len(sentiment_results)
        }
        
        return {
            "total_tickets": len(sentiment_results),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "average_sentiment": avg_sentiment,
            "average_confidence": avg_confidence,
            "sentiment_distribution": sentiment_distribution,
            "confidence_distribution": confidence_distribution
        }
    
    def detect_sentiment_anomalies(self, sentiment_results: List[Dict[str, any]], 
                                 threshold: float = 2.0) -> List[Dict[str, any]]:
        """
        Detect sentiment anomalies (unusually positive or negative tickets)
        
        Args:
            sentiment_results: List of sentiment analysis results
            threshold: Standard deviation threshold for anomaly detection
            
        Returns:
            List of anomalous sentiment results
        """
        if len(sentiment_results) < 3:
            return []
        
        sentiment_scores = [result['sentiment_score'] for result in sentiment_results]
        mean_sentiment = np.mean(sentiment_scores)
        std_sentiment = np.std(sentiment_scores)
        
        anomalies = []
        for result in sentiment_results:
            score = result['sentiment_score']
            z_score = abs(score - mean_sentiment) / std_sentiment if std_sentiment > 0 else 0
            
            if z_score > threshold:
                result_copy = result.copy()
                result_copy['z_score'] = z_score
                result_copy['is_anomaly'] = True
                anomalies.append(result_copy)
        
        return anomalies

# Global sentiment analyzer instance
sentiment_analyzer = SentimentAnalyzer() 