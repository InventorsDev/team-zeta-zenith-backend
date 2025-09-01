from typing import List, Dict, Any, Tuple
import logging
from collections import Counter

logger = logging.getLogger(__name__)

class ModelEvaluator:
    """
    Evaluation framework for ML models (simplified version without sklearn dependency)
    """
    
    def __init__(self):
        self.metrics_history = []
    
    def calculate_classification_metrics(self, y_true: List[str], y_pred: List[str], 
                                       categories: List[str] = None) -> Dict[str, Any]:
        """
        Calculate classification metrics without sklearn dependency
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            categories: List of categories (optional)
            
        Returns:
            Dictionary with evaluation metrics
        """
        if len(y_true) != len(y_pred):
            raise ValueError("y_true and y_pred must have the same length")
        
        if not y_true:
            return {
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "support": 0,
                "per_category": {}
            }
        
        # Calculate accuracy
        correct = sum(1 for true, pred in zip(y_true, y_pred) if true == pred)
        accuracy = correct / len(y_true)
        
        # Get unique categories
        if categories is None:
            categories = list(set(y_true + y_pred))
        
        # Calculate per-category metrics
        per_category = {}
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        total_support = 0
        
        for category in categories:
            # True positives, false positives, false negatives
            tp = sum(1 for true, pred in zip(y_true, y_pred) if true == category and pred == category)
            fp = sum(1 for true, pred in zip(y_true, y_pred) if true != category and pred == category)
            fn = sum(1 for true, pred in zip(y_true, y_pred) if true == category and pred != category)
            
            # Calculate metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            support = tp + fn
            
            per_category[category] = {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": support
            }
            
            # Weighted averages
            total_precision += precision * support
            total_recall += recall * support
            total_f1 += f1 * support
            total_support += support
        
        # Calculate weighted averages
        weighted_precision = total_precision / total_support if total_support > 0 else 0.0
        weighted_recall = total_recall / total_support if total_support > 0 else 0.0
        weighted_f1 = total_f1 / total_support if total_support > 0 else 0.0
        
        metrics = {
            "accuracy": accuracy,
            "precision": weighted_precision,
            "recall": weighted_recall,
            "f1_score": weighted_f1,
            "support": total_support,
            "per_category": per_category,
            "total_samples": len(y_true)
        }
        
        # Store metrics in history
        self.metrics_history.append({
            "timestamp": "now",
            "metrics": metrics
        })
        
        return metrics
    
    def calculate_sentiment_metrics(self, y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
        """
        Calculate sentiment analysis metrics
        
        Args:
            y_true: True sentiment labels
            y_pred: Predicted sentiment labels
            
        Returns:
            Dictionary with sentiment evaluation metrics
        """
        # Convert sentiment scores to labels if needed
        y_true_labels = self._convert_sentiment_scores_to_labels(y_true)
        y_pred_labels = self._convert_sentiment_scores_to_labels(y_pred)
        
        return self.calculate_classification_metrics(y_true_labels, y_pred_labels, 
                                                   categories=['positive', 'negative', 'neutral'])
    
    def _convert_sentiment_scores_to_labels(self, sentiments: List) -> List[str]:
        """
        Convert sentiment scores to labels
        
        Args:
            sentiments: List of sentiment scores or labels
            
        Returns:
            List of sentiment labels
        """
        labels = []
        for sentiment in sentiments:
            if isinstance(sentiment, (int, float)):
                # Convert score to label
                if sentiment > 0.05:
                    labels.append('positive')
                elif sentiment < -0.05:
                    labels.append('negative')
                else:
                    labels.append('neutral')
            else:
                # Already a label
                labels.append(str(sentiment).lower())
        
        return labels
    
    def calculate_confidence_metrics(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate confidence distribution metrics
        
        Args:
            predictions: List of prediction dictionaries with confidence scores
            
        Returns:
            Dictionary with confidence metrics
        """
        if not predictions:
            return {
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "high_confidence_rate": 0.0,
                "low_confidence_rate": 0.0
            }
        
        confidence_scores = [pred.get('confidence', 0.0) for pred in predictions]
        
        # Calculate basic statistics
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Calculate confidence distribution
        high_conf = sum(1 for conf in confidence_scores if conf >= 0.7)
        medium_conf = sum(1 for conf in confidence_scores if 0.4 <= conf < 0.7)
        low_conf = sum(1 for conf in confidence_scores if conf < 0.4)
        
        total = len(confidence_scores)
        
        confidence_distribution = {
            "high": high_conf / total,
            "medium": medium_conf / total,
            "low": low_conf / total
        }
        
        return {
            "average_confidence": avg_confidence,
            "confidence_distribution": confidence_distribution,
            "high_confidence_rate": high_conf / total,
            "low_confidence_rate": low_conf / total,
            "total_predictions": total
        }
    
    def compare_models(self, model_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare multiple models
        
        Args:
            model_results: Dictionary with model names as keys and metrics as values
            
        Returns:
            Comparison results
        """
        comparison = {
            "models": list(model_results.keys()),
            "best_model": None,
            "comparison_metrics": {}
        }
        
        if not model_results:
            return comparison
        
        # Compare accuracy
        accuracies = {name: metrics.get('accuracy', 0.0) for name, metrics in model_results.items()}
        best_accuracy_model = max(accuracies, key=accuracies.get)
        
        # Compare F1 scores
        f1_scores = {name: metrics.get('f1_score', 0.0) for name, metrics in model_results.items()}
        best_f1_model = max(f1_scores, key=f1_scores.get)
        
        comparison["best_model"] = {
            "by_accuracy": best_accuracy_model,
            "by_f1_score": best_f1_model
        }
        
        comparison["comparison_metrics"] = {
            "accuracies": accuracies,
            "f1_scores": f1_scores,
            "precision_scores": {name: metrics.get('precision', 0.0) for name, metrics in model_results.items()},
            "recall_scores": {name: metrics.get('recall', 0.0) for name, metrics in model_results.items()}
        }
        
        return comparison
    
    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """
        Get metrics history
        
        Returns:
            List of historical metrics
        """
        return self.metrics_history
    
    def export_metrics_report(self, metrics: Dict[str, Any], filename: str = None) -> str:
        """
        Export metrics to a formatted report
        
        Args:
            metrics: Metrics dictionary
            filename: Output filename (optional)
            
        Returns:
            Report content
        """
        report = []
        report.append("=" * 50)
        report.append("MODEL EVALUATION REPORT")
        report.append("=" * 50)
        report.append("")
        
        # Overall metrics
        report.append("OVERALL METRICS:")
        report.append(f"Accuracy: {metrics.get('accuracy', 0.0):.4f}")
        report.append(f"Precision: {metrics.get('precision', 0.0):.4f}")
        report.append(f"Recall: {metrics.get('recall', 0.0):.4f}")
        report.append(f"F1 Score: {metrics.get('f1_score', 0.0):.4f}")
        report.append(f"Total Samples: {metrics.get('total_samples', 0)}")
        report.append("")
        
        # Per-category metrics
        if metrics.get('per_category'):
            report.append("PER-CATEGORY METRICS:")
            for category, cat_metrics in metrics['per_category'].items():
                report.append(f"\n{category.upper()}:")
                report.append(f"  Precision: {cat_metrics.get('precision', 0.0):.4f}")
                report.append(f"  Recall: {cat_metrics.get('recall', 0.0):.4f}")
                report.append(f"  F1 Score: {cat_metrics.get('f1_score', 0.0):.4f}")
                report.append(f"  Support: {cat_metrics.get('support', 0)}")
        
        report_content = "\n".join(report)
        
        if filename:
            with open(filename, 'w') as f:
                f.write(report_content)
        
        return report_content

# Global evaluator instance
model_evaluator = ModelEvaluator() 