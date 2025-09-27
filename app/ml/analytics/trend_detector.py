import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

logger = logging.getLogger(__name__)

class TrendDetector:
    """
    Trend detection for support ticket categories and sentiment
    Implements anomaly detection and percentage change calculations
    """
    
    def __init__(self):
        self.trend_history = []
        self.anomaly_threshold = 2.0  # Standard deviations for anomaly detection
        self.significance_thresholds = {
            "low": 0.1,      # 10% change
            "medium": 0.25,  # 25% change
            "high": 0.5      # 50% change
        }
    
    def calculate_volume_trends(self, tickets: List[Dict[str, Any]], 
                               time_period: str = "daily") -> Dict[str, Any]:
        """
        Calculate volume trends for ticket categories
        
        Args:
            tickets: List of ticket dictionaries with timestamps
            time_period: Time period for grouping ("daily", "weekly", "monthly")
            
        Returns:
            Dictionary with trend analysis
        """
        try:
            # Convert to DataFrame
            df = pd.DataFrame(tickets)
            
            # Add timestamp if not present
            if 'timestamp' not in df.columns:
                df['timestamp'] = datetime.now()
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Group by time period and category
            if time_period == "daily":
                df['period'] = df['timestamp'].dt.date
            elif time_period == "weekly":
                df['period'] = df['timestamp'].dt.to_period('W')
            elif time_period == "monthly":
                df['period'] = df['timestamp'].dt.to_period('M')
            
            # Calculate volume by period and category
            volume_data = df.groupby(['period', 'category']).size().unstack(fill_value=0)
            
            # Calculate trends for each category
            trends = {}
            for category in volume_data.columns:
                category_trends = self._calculate_category_trends(volume_data[category])
                trends[category] = category_trends
            
            # Calculate overall trends
            total_volume = volume_data.sum(axis=1)
            overall_trends = self._calculate_category_trends(total_volume)
            
            result = {
                "time_period": time_period,
                "total_tickets": len(tickets),
                "periods_analyzed": len(volume_data),
                "category_trends": trends,
                "overall_trends": overall_trends,
                "volume_data": volume_data.to_dict()
            }
            
            # Store in history
            self.trend_history.append({
                "timestamp": datetime.now().isoformat(),
                "analysis_type": "volume_trends",
                "result": result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Volume trend calculation failed: {e}")
            raise
    
    def _calculate_category_trends(self, series: pd.Series) -> Dict[str, Any]:
        """Calculate trends for a specific category"""
        if len(series) < 2:
            return {
                "trend": "insufficient_data",
                "percentage_change": 0.0,
                "significance": "low",
                "anomalies": [],
                "mean": series.mean() if len(series) > 0 else 0,
                "std": series.std() if len(series) > 1 else 0
            }
        
        # Calculate percentage change
        current = series.iloc[-1]
        previous = series.iloc[-2]
        
        if previous == 0:
            percentage_change = float('inf') if current > 0 else 0.0
        else:
            percentage_change = (current - previous) / previous
        
        # Determine trend direction
        if percentage_change > 0.05:
            trend = "increasing"
        elif percentage_change < -0.05:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Calculate significance
        significance = self._calculate_significance(abs(percentage_change))
        
        # Detect anomalies
        anomalies = self._detect_anomalies(series)
        
        return {
            "trend": trend,
            "percentage_change": percentage_change,
            "significance": significance,
            "anomalies": anomalies,
            "mean": series.mean(),
            "std": series.std(),
            "current_value": current,
            "previous_value": previous
        }
    
    def _calculate_significance(self, percentage_change: float) -> str:
        """Calculate significance level of a change"""
        if percentage_change >= self.significance_thresholds["high"]:
            return "high"
        elif percentage_change >= self.significance_thresholds["medium"]:
            return "medium"
        elif percentage_change >= self.significance_thresholds["low"]:
            return "low"
        else:
            return "insignificant"
    
    def _detect_anomalies(self, series: pd.Series) -> List[Dict[str, Any]]:
        """Detect anomalies in time series data"""
        if len(series) < 3:
            return []
        
        mean = series.mean()
        std = series.std()
        
        if std == 0:
            return []
        
        anomalies = []
        for i, value in enumerate(series):
            z_score = abs(value - mean) / std
            
            if z_score > self.anomaly_threshold:
                anomalies.append({
                    "index": i,
                    "value": value,
                    "z_score": z_score,
                    "period": series.index[i] if hasattr(series.index[i], 'isoformat') else str(series.index[i])
                })
        
        return anomalies
    
    def calculate_sentiment_trends(self, tickets: List[Dict[str, Any]], 
                                 time_period: str = "daily") -> Dict[str, Any]:
        """
        Calculate sentiment trends over time
        
        Args:
            tickets: List of ticket dictionaries with sentiment scores
            time_period: Time period for grouping
            
        Returns:
            Dictionary with sentiment trend analysis
        """
        try:
            # Convert to DataFrame
            df = pd.DataFrame(tickets)
            
            # Add timestamp if not present
            if 'timestamp' not in df.columns:
                df['timestamp'] = datetime.now()
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Group by time period
            if time_period == "daily":
                df['period'] = df['timestamp'].dt.date
            elif time_period == "weekly":
                df['period'] = df['timestamp'].dt.to_period('W')
            elif time_period == "monthly":
                df['period'] = df['timestamp'].dt.to_period('M')
            
            # Calculate sentiment metrics by period
            sentiment_data = df.groupby('period').agg({
                'sentiment_score': ['mean', 'std', 'count'],
                'sentiment': lambda x: x.value_counts().to_dict()
            }).round(3)
            
            # Calculate sentiment trends
            sentiment_series = sentiment_data[('sentiment_score', 'mean')]
            sentiment_trends = self._calculate_category_trends(sentiment_series)
            
            # Calculate sentiment distribution trends
            sentiment_distribution = self._calculate_sentiment_distribution_trends(df)
            
            result = {
                "time_period": time_period,
                "total_tickets": len(tickets),
                "periods_analyzed": len(sentiment_data),
                "sentiment_trends": sentiment_trends,
                "sentiment_distribution": sentiment_distribution,
                "sentiment_data": sentiment_data.to_dict()
            }
            
            # Store in history
            self.trend_history.append({
                "timestamp": datetime.now().isoformat(),
                "analysis_type": "sentiment_trends",
                "result": result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Sentiment trend calculation failed: {e}")
            raise
    
    def _calculate_sentiment_distribution_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate trends in sentiment distribution"""
        # Get sentiment distribution
        sentiment_counts = df['sentiment'].value_counts()
        total_tickets = len(df)
        
        distribution = {
            sentiment: {
                "count": count,
                "percentage": (count / total_tickets) * 100
            }
            for sentiment, count in sentiment_counts.items()
        }
        
        # Calculate sentiment balance
        positive_count = sentiment_counts.get('positive', 0)
        negative_count = sentiment_counts.get('negative', 0)
        neutral_count = sentiment_counts.get('neutral', 0)
        
        if positive_count + negative_count > 0:
            sentiment_balance = (positive_count - negative_count) / (positive_count + negative_count)
        else:
            sentiment_balance = 0.0
        
        return {
            "distribution": distribution,
            "sentiment_balance": sentiment_balance,
            "total_tickets": total_tickets
        }
    
    def detect_anomalies(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies in ticket patterns
        
        Args:
            tickets: List of ticket dictionaries
            
        Returns:
            Dictionary with anomaly detection results
        """
        try:
            df = pd.DataFrame(tickets)
            
            anomalies = {
                "volume_anomalies": [],
                "sentiment_anomalies": [],
                "category_anomalies": [],
                "confidence_anomalies": []
            }
            
            # Volume anomalies (if timestamps available)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp'].dt.hour
                
                # Detect unusual volume by hour
                hourly_volume = df.groupby('hour').size()
                if len(hourly_volume) > 1:
                    mean_volume = hourly_volume.mean()
                    std_volume = hourly_volume.std()
                    
                    for hour, volume in hourly_volume.items():
                        if std_volume > 0:
                            z_score = abs(volume - mean_volume) / std_volume
                            if z_score > self.anomaly_threshold:
                                anomalies["volume_anomalies"].append({
                                    "type": "hourly_volume",
                                    "hour": hour,
                                    "volume": volume,
                                    "z_score": z_score,
                                    "expected_range": f"{mean_volume - std_volume:.1f} - {mean_volume + std_volume:.1f}"
                                })
            
            # Sentiment anomalies
            if 'sentiment_score' in df.columns:
                sentiment_scores = df['sentiment_score'].dropna()
                if len(sentiment_scores) > 1:
                    mean_sentiment = sentiment_scores.mean()
                    std_sentiment = sentiment_scores.std()
                    
                    for idx, score in sentiment_scores.items():
                        if std_sentiment > 0:
                            z_score = abs(score - mean_sentiment) / std_sentiment
                            if z_score > self.anomaly_threshold:
                                anomalies["sentiment_anomalies"].append({
                                    "type": "sentiment_score",
                                    "ticket_index": idx,
                                    "score": score,
                                    "z_score": z_score,
                                    "expected_range": f"{mean_sentiment - std_sentiment:.3f} - {mean_sentiment + std_sentiment:.3f}"
                                })
            
            # Category anomalies
            if 'category' in df.columns:
                category_counts = df['category'].value_counts()
                total_tickets = len(df)
                
                for category, count in category_counts.items():
                    expected_percentage = 1 / len(category_counts)  # Assume uniform distribution
                    actual_percentage = count / total_tickets
                    
                    if abs(actual_percentage - expected_percentage) > 0.3:  # 30% deviation
                        anomalies["category_anomalies"].append({
                            "type": "category_distribution",
                            "category": category,
                            "count": count,
                            "percentage": actual_percentage * 100,
                            "expected_percentage": expected_percentage * 100,
                            "deviation": (actual_percentage - expected_percentage) * 100
                        })
            
            # Confidence anomalies
            if 'confidence' in df.columns:
                confidence_scores = df['confidence'].dropna()
                if len(confidence_scores) > 1:
                    mean_confidence = confidence_scores.mean()
                    std_confidence = confidence_scores.std()
                    
                    for idx, confidence in confidence_scores.items():
                        if std_confidence > 0:
                            z_score = abs(confidence - mean_confidence) / std_confidence
                            if z_score > self.anomaly_threshold:
                                anomalies["confidence_anomalies"].append({
                                    "type": "confidence_score",
                                    "ticket_index": idx,
                                    "confidence": confidence,
                                    "z_score": z_score,
                                    "expected_range": f"{mean_confidence - std_confidence:.3f} - {mean_confidence + std_confidence:.3f}"
                                })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            raise
    
    def generate_alerts(self, trends: Dict[str, Any], 
                       alert_thresholds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Generate alerts based on trend analysis
        
        Args:
            trends: Trend analysis results
            alert_thresholds: Custom alert thresholds
            
        Returns:
            List of alerts
        """
        if alert_thresholds is None:
            alert_thresholds = {
                "volume_increase": 0.5,    # 50% increase
                "volume_decrease": -0.3,   # 30% decrease
                "sentiment_drop": -0.2,    # 20% sentiment drop
                "anomaly_count": 3         # 3 or more anomalies
            }
        
        alerts = []
        
        # Volume alerts
        if "overall_trends" in trends:
            overall = trends["overall_trends"]
            if overall["percentage_change"] > alert_thresholds["volume_increase"]:
                alerts.append({
                    "type": "volume_increase",
                    "severity": "high" if overall["significance"] == "high" else "medium",
                    "message": f"Ticket volume increased by {overall['percentage_change']:.1%}",
                    "percentage_change": overall["percentage_change"],
                    "significance": overall["significance"]
                })
            elif overall["percentage_change"] < alert_thresholds["volume_decrease"]:
                alerts.append({
                    "type": "volume_decrease",
                    "severity": "high" if overall["significance"] == "high" else "medium",
                    "message": f"Ticket volume decreased by {abs(overall['percentage_change']):.1%}",
                    "percentage_change": overall["percentage_change"],
                    "significance": overall["significance"]
                })
        
        # Category-specific alerts
        if "category_trends" in trends:
            for category, category_trends in trends["category_trends"].items():
                if category_trends["percentage_change"] > alert_thresholds["volume_increase"]:
                    alerts.append({
                        "type": "category_increase",
                        "category": category,
                        "severity": "medium",
                        "message": f"{category} tickets increased by {category_trends['percentage_change']:.1%}",
                        "percentage_change": category_trends["percentage_change"]
                    })
        
        # Anomaly alerts
        total_anomalies = sum(len(anomalies) for anomalies in trends.get("anomalies", {}).values())
        if total_anomalies >= alert_thresholds["anomaly_count"]:
            alerts.append({
                "type": "anomaly_detected",
                "severity": "high",
                "message": f"Detected {total_anomalies} anomalies in ticket patterns",
                "anomaly_count": total_anomalies
            })
        
        return alerts
    
    def get_trend_history(self) -> List[Dict[str, Any]]:
        """Get trend analysis history"""
        return self.trend_history

# Global trend detector instance
trend_detector = TrendDetector() 