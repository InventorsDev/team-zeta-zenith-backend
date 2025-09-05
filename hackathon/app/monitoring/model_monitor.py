import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)

class ModelMonitor:
    """
    Model monitoring and performance tracking
    Implements drift detection and automated retraining triggers
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.monitoring_data = defaultdict(list)
        self.performance_history = []
        self.drift_alerts = []
        self.retraining_triggers = []
        
        # Monitoring thresholds
        self.accuracy_threshold = 0.75  # 75% accuracy threshold
        self.confidence_threshold = 0.6  # 60% average confidence threshold
        self.drift_threshold = 0.1  # 10% performance degradation
        self.retraining_interval = 30  # Days between retraining
        
        # Create monitoring directory
        os.makedirs(models_dir, exist_ok=True)
        self.monitoring_file = os.path.join(models_dir, "monitoring_data.json")
        self._load_monitoring_data()
    
    def _load_monitoring_data(self):
        """Load existing monitoring data"""
        try:
            if os.path.exists(self.monitoring_file):
                with open(self.monitoring_file, 'r') as f:
                    data = json.load(f)
                    self.monitoring_data = defaultdict(list, data.get('monitoring_data', {}))
                    self.performance_history = data.get('performance_history', [])
                    self.drift_alerts = data.get('drift_alerts', [])
                    self.retraining_triggers = data.get('retraining_triggers', [])
                logger.info("Loaded existing monitoring data")
        except Exception as e:
            logger.warning(f"Could not load monitoring data: {e}")
    
    def _save_monitoring_data(self):
        """Save monitoring data to file"""
        try:
            data = {
                'monitoring_data': dict(self.monitoring_data),
                'performance_history': self.performance_history,
                'drift_alerts': self.drift_alerts,
                'retraining_triggers': self.retraining_triggers,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.monitoring_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save monitoring data: {e}")
    
    def track_prediction(self, model_name: str, prediction: Dict[str, Any], 
                        ground_truth: str = None, timestamp: datetime = None):
        """
        Track a single prediction for monitoring
        
        Args:
            model_name: Name of the model
            prediction: Prediction result dictionary
            ground_truth: True label (optional)
            timestamp: Prediction timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        tracking_data = {
            'timestamp': timestamp.isoformat(),
            'model_name': model_name,
            'prediction': prediction,
            'ground_truth': ground_truth,
            'correct': ground_truth == prediction.get('category') if ground_truth else None
        }
        
        self.monitoring_data[model_name].append(tracking_data)
        
        # Keep only last 1000 predictions per model
        if len(self.monitoring_data[model_name]) > 1000:
            self.monitoring_data[model_name] = self.monitoring_data[model_name][-1000:]
        
        self._save_monitoring_data()
    
    def calculate_performance_metrics(self, model_name: str, 
                                    time_window: int = 7) -> Dict[str, Any]:
        """
        Calculate performance metrics for a model
        
        Args:
            model_name: Name of the model
            time_window: Number of days to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        if model_name not in self.monitoring_data:
            return {
                'model_name': model_name,
                'total_predictions': 0,
                'accuracy': 0.0,
                'average_confidence': 0.0,
                'confidence_distribution': {},
                'category_distribution': {},
                'recent_performance': {}
            }
        
        # Filter data by time window
        cutoff_date = datetime.now() - timedelta(days=time_window)
        recent_data = [
            data for data in self.monitoring_data[model_name]
            if datetime.fromisoformat(data['timestamp']) >= cutoff_date
        ]
        
        if not recent_data:
            return {
                'model_name': model_name,
                'total_predictions': 0,
                'accuracy': 0.0,
                'average_confidence': 0.0,
                'confidence_distribution': {},
                'category_distribution': {},
                'recent_performance': {}
            }
        
        # Calculate accuracy
        correct_predictions = sum(1 for data in recent_data if data.get('correct') is True)
        total_with_ground_truth = sum(1 for data in recent_data if data.get('correct') is not None)
        accuracy = correct_predictions / total_with_ground_truth if total_with_ground_truth > 0 else 0.0
        
        # Calculate confidence metrics
        confidences = [data['prediction'].get('confidence', 0.0) for data in recent_data]
        average_confidence = np.mean(confidences) if confidences else 0.0
        
        # Confidence distribution
        confidence_distribution = {
            'high': sum(1 for conf in confidences if conf >= 0.8),
            'medium': sum(1 for conf in confidences if 0.6 <= conf < 0.8),
            'low': sum(1 for conf in confidences if conf < 0.6)
        }
        
        # Category distribution
        categories = [data['prediction'].get('category', 'unknown') for data in recent_data]
        category_counts = defaultdict(int)
        for category in categories:
            category_counts[category] += 1
        
        category_distribution = dict(category_counts)
        
        # Recent performance (last 24 hours)
        day_cutoff = datetime.now() - timedelta(days=1)
        day_data = [
            data for data in recent_data
            if datetime.fromisoformat(data['timestamp']) >= day_cutoff
        ]
        
        day_correct = sum(1 for data in day_data if data.get('correct') is True)
        day_total = sum(1 for data in day_data if data.get('correct') is not None)
        day_accuracy = day_correct / day_total if day_total > 0 else 0.0
        
        metrics = {
            'model_name': model_name,
            'total_predictions': len(recent_data),
            'accuracy': accuracy,
            'average_confidence': average_confidence,
            'confidence_distribution': confidence_distribution,
            'category_distribution': category_distribution,
            'recent_performance': {
                'last_24h_accuracy': day_accuracy,
                'last_24h_predictions': len(day_data)
            },
            'time_window_days': time_window
        }
        
        # Store in performance history
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'model_name': model_name,
            'metrics': metrics
        })
        
        # Keep only last 100 performance records
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
        
        self._save_monitoring_data()
        return metrics
    
    def detect_model_drift(self, model_name: str) -> Dict[str, Any]:
        """
        Detect model drift by comparing recent vs historical performance
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with drift detection results
        """
        if len(self.performance_history) < 2:
            return {
                'model_name': model_name,
                'drift_detected': False,
                'drift_score': 0.0,
                'recent_accuracy': 0.0,
                'historical_accuracy': 0.0,
                'drift_alerts': []
            }
        
        # Get recent performance (last 7 days)
        recent_metrics = self.calculate_performance_metrics(model_name, time_window=7)
        recent_accuracy = recent_metrics['accuracy']
        
        # Get historical performance (last 30 days, excluding recent)
        historical_metrics = self.calculate_performance_metrics(model_name, time_window=30)
        historical_accuracy = historical_metrics['accuracy']
        
        # Calculate drift score
        if historical_accuracy > 0:
            drift_score = (historical_accuracy - recent_accuracy) / historical_accuracy
        else:
            drift_score = 0.0
        
        # Determine if drift is detected
        drift_detected = drift_score > self.drift_threshold
        
        # Generate drift alerts
        drift_alerts = []
        if drift_detected:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'model_name': model_name,
                'type': 'performance_drift',
                'severity': 'high' if drift_score > 0.2 else 'medium',
                'message': f"Model drift detected: {drift_score:.1%} performance degradation",
                'drift_score': drift_score,
                'recent_accuracy': recent_accuracy,
                'historical_accuracy': historical_accuracy
            }
            drift_alerts.append(alert)
            self.drift_alerts.append(alert)
        
        # Check confidence drift
        recent_confidence = recent_metrics['average_confidence']
        historical_confidence = historical_metrics['average_confidence']
        
        if historical_confidence > 0:
            confidence_drift = (historical_confidence - recent_confidence) / historical_confidence
            if confidence_drift > self.drift_threshold:
                alert = {
                    'timestamp': datetime.now().isoformat(),
                    'model_name': model_name,
                    'type': 'confidence_drift',
                    'severity': 'medium',
                    'message': f"Confidence drift detected: {confidence_drift:.1%} confidence degradation",
                    'drift_score': confidence_drift,
                    'recent_confidence': recent_confidence,
                    'historical_confidence': historical_confidence
                }
                drift_alerts.append(alert)
                self.drift_alerts.append(alert)
        
        # Keep only last 100 drift alerts
        if len(self.drift_alerts) > 100:
            self.drift_alerts = self.drift_alerts[-100:]
        
        self._save_monitoring_data()
        
        return {
            'model_name': model_name,
            'drift_detected': drift_detected,
            'drift_score': drift_score,
            'recent_accuracy': recent_accuracy,
            'historical_accuracy': historical_accuracy,
            'recent_confidence': recent_confidence,
            'historical_confidence': historical_confidence,
            'drift_alerts': drift_alerts
        }
    
    def check_retraining_triggers(self, model_name: str) -> Dict[str, Any]:
        """
        Check if model retraining is needed
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with retraining trigger results
        """
        triggers = []
        retraining_needed = False
        
        # Get current performance
        current_metrics = self.calculate_performance_metrics(model_name, time_window=7)
        
        # Check accuracy threshold
        if current_metrics['accuracy'] < self.accuracy_threshold:
            triggers.append({
                'type': 'low_accuracy',
                'severity': 'high',
                'message': f"Accuracy below threshold: {current_metrics['accuracy']:.1%} < {self.accuracy_threshold:.1%}",
                'current_value': current_metrics['accuracy'],
                'threshold': self.accuracy_threshold
            })
            retraining_needed = True
        
        # Check confidence threshold
        if current_metrics['average_confidence'] < self.confidence_threshold:
            triggers.append({
                'type': 'low_confidence',
                'severity': 'medium',
                'message': f"Average confidence below threshold: {current_metrics['average_confidence']:.1%} < {self.confidence_threshold:.1%}",
                'current_value': current_metrics['average_confidence'],
                'threshold': self.confidence_threshold
            })
            retraining_needed = True
        
        # Check for model drift
        drift_results = self.detect_model_drift(model_name)
        if drift_results['drift_detected']:
            triggers.append({
                'type': 'model_drift',
                'severity': 'high',
                'message': f"Model drift detected: {drift_results['drift_score']:.1%} performance degradation",
                'drift_score': drift_results['drift_score'],
                'threshold': self.drift_threshold
            })
            retraining_needed = True
        
        # Check time-based retraining
        last_retraining = self._get_last_retraining_date(model_name)
        if last_retraining:
            days_since_retraining = (datetime.now() - last_retraining).days
            if days_since_retraining > self.retraining_interval:
                triggers.append({
                    'type': 'time_based',
                    'severity': 'low',
                    'message': f"Time-based retraining: {days_since_retraining} days since last retraining",
                    'days_since_retraining': days_since_retraining,
                    'threshold': self.retraining_interval
                })
                retraining_needed = True
        
        # Store retraining trigger
        if retraining_needed:
            trigger_record = {
                'timestamp': datetime.now().isoformat(),
                'model_name': model_name,
                'triggers': triggers,
                'retraining_needed': retraining_needed
            }
            self.retraining_triggers.append(trigger_record)
            
            # Keep only last 50 retraining triggers
            if len(self.retraining_triggers) > 50:
                self.retraining_triggers = self.retraining_triggers[-50:]
        
        self._save_monitoring_data()
        
        return {
            'model_name': model_name,
            'retraining_needed': retraining_needed,
            'triggers': triggers,
            'current_metrics': current_metrics
        }
    
    def _get_last_retraining_date(self, model_name: str) -> Optional[datetime]:
        """Get the last retraining date for a model"""
        # Look for retraining triggers in reverse order
        for trigger in reversed(self.retraining_triggers):
            if trigger['model_name'] == model_name and trigger['retraining_needed']:
                return datetime.fromisoformat(trigger['timestamp'])
        return None
    
    def get_model_health_dashboard(self, model_name: str) -> Dict[str, Any]:
        """
        Get comprehensive model health dashboard
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with health dashboard data
        """
        # Get performance metrics
        performance_metrics = self.calculate_performance_metrics(model_name)
        
        # Get drift detection results
        drift_results = self.detect_model_drift(model_name)
        
        # Get retraining trigger results
        retraining_results = self.check_retraining_triggers(model_name)
        
        # Calculate overall health score
        health_score = self._calculate_health_score(performance_metrics, drift_results, retraining_results)
        
        # Get recent alerts
        recent_alerts = [
            alert for alert in self.drift_alerts
            if alert['model_name'] == model_name and 
            datetime.fromisoformat(alert['timestamp']) >= datetime.now() - timedelta(days=7)
        ]
        
        return {
            'model_name': model_name,
            'health_score': health_score,
            'status': self._get_model_status(health_score),
            'performance_metrics': performance_metrics,
            'drift_detection': drift_results,
            'retraining_status': retraining_results,
            'recent_alerts': recent_alerts,
            'last_updated': datetime.now().isoformat()
        }
    
    def _calculate_health_score(self, performance_metrics: Dict, 
                               drift_results: Dict, retraining_results: Dict) -> float:
        """Calculate overall model health score (0-100)"""
        score = 100.0
        
        # Deduct points for low accuracy
        if performance_metrics['accuracy'] < self.accuracy_threshold:
            score -= 30
        
        # Deduct points for low confidence
        if performance_metrics['average_confidence'] < self.confidence_threshold:
            score -= 20
        
        # Deduct points for model drift
        if drift_results['drift_detected']:
            score -= 25
        
        # Deduct points for retraining needed
        if retraining_results['retraining_needed']:
            score -= 15
        
        return max(0.0, score)
    
    def _get_model_status(self, health_score: float) -> str:
        """Get model status based on health score"""
        if health_score >= 80:
            return "healthy"
        elif health_score >= 60:
            return "degraded"
        elif health_score >= 40:
            return "poor"
        else:
            return "critical"
    
    def get_all_models_health(self) -> Dict[str, Any]:
        """Get health status for all monitored models"""
        models = list(self.monitoring_data.keys())
        health_data = {}
        
        for model_name in models:
            health_data[model_name] = self.get_model_health_dashboard(model_name)
        
        # Calculate overall system health
        if health_data:
            overall_health_score = np.mean([data['health_score'] for data in health_data.values()])
            overall_status = self._get_model_status(overall_health_score)
        else:
            overall_health_score = 100.0
            overall_status = "healthy"
        
        return {
            'overall_health_score': overall_health_score,
            'overall_status': overall_status,
            'models': health_data,
            'total_models': len(models),
            'last_updated': datetime.now().isoformat()
        }
    
    def export_monitoring_report(self, output_file: str = None) -> str:
        """Export comprehensive monitoring report"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.models_dir, f"monitoring_report_{timestamp}.json")
        
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'all_models_health': self.get_all_models_health(),
            'performance_history': self.performance_history[-50:],  # Last 50 records
            'drift_alerts': self.drift_alerts[-20:],  # Last 20 alerts
            'retraining_triggers': self.retraining_triggers[-10:],  # Last 10 triggers
            'monitoring_summary': {
                'total_predictions_tracked': sum(len(data) for data in self.monitoring_data.values()),
                'total_models_monitored': len(self.monitoring_data),
                'total_drift_alerts': len(self.drift_alerts),
                'total_retraining_triggers': len(self.retraining_triggers)
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Monitoring report exported to: {output_file}")
        return output_file

# Global model monitor instance
model_monitor = ModelMonitor() 