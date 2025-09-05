#!/usr/bin/env python3
"""
Test script to compare accuracy between original and enhanced classifiers
"""

import json
import time
from typing import List, Dict, Any

def load_test_data():
    """Load test data from sample tickets"""
    with open('data/sample_tickets.json', 'r') as f:
        return json.load(f)

def test_original_classifier():
    """Test the original rule-based classifier"""
    print("Testing Original Classifier...")
    
    from app.models.rule_based_classifier import rule_based_classifier
    from app.models.evaluation import model_evaluator
    
    # Load test data
    test_data = load_test_data()
    
    # Prepare test data
    y_true = [ticket['category'] for ticket in test_data]
    y_pred = []
    predictions = []
    
    start_time = time.time()
    
    for ticket in test_data:
        result = rule_based_classifier.classify_with_confidence_label(ticket['text'])
        y_pred.append(result['category'])
        predictions.append(result)
    
    processing_time = time.time() - start_time
    
    # Calculate metrics
    metrics = model_evaluator.calculate_classification_metrics(y_true, y_pred)
    confidence_metrics = model_evaluator.calculate_confidence_metrics(predictions)
    
    print(f"Processing Time: {processing_time:.3f}s")
    print(f"Accuracy: {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1 Score: {metrics['f1_score']:.3f}")
    print(f"Average Confidence: {confidence_metrics['average_confidence']:.3f}")
    print(f"High Confidence Rate: {confidence_metrics['high_confidence_rate']:.3f}")
    
    return metrics, confidence_metrics, predictions

def test_enhanced_classifier():
    """Test the enhanced classifier"""
    print("\nTesting Enhanced Classifier...")
    
    from app.models.enhanced_classifier import enhanced_classifier
    from app.models.evaluation import model_evaluator
    
    # Load test data
    test_data = load_test_data()
    
    # Prepare test data
    y_true = [ticket['category'] for ticket in test_data]
    y_pred = []
    predictions = []
    
    start_time = time.time()
    
    for ticket in test_data:
        result = enhanced_classifier.classify_with_confidence_label(ticket['text'])
        y_pred.append(result['category'])
        predictions.append(result)
    
    processing_time = time.time() - start_time
    
    # Calculate metrics
    metrics = model_evaluator.calculate_classification_metrics(y_true, y_pred)
    confidence_metrics = model_evaluator.calculate_confidence_metrics(predictions)
    
    print(f"Processing Time: {processing_time:.3f}s")
    print(f"Accuracy: {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1 Score: {metrics['f1_score']:.3f}")
    print(f"Average Confidence: {confidence_metrics['average_confidence']:.3f}")
    print(f"High Confidence Rate: {confidence_metrics['high_confidence_rate']:.3f}")
    
    return metrics, confidence_metrics, predictions

def compare_results(original_metrics, original_confidence, original_predictions,
                   enhanced_metrics, enhanced_confidence, enhanced_predictions):
    """Compare results between classifiers"""
    print("\n" + "="*60)
    print("ACCURACY COMPARISON RESULTS")
    print("="*60)
    
    # Compare metrics
    print("\n📊 METRICS COMPARISON:")
    print(f"{'Metric':<15} {'Original':<10} {'Enhanced':<10} {'Improvement':<12}")
    print("-" * 50)
    
    accuracy_improvement = enhanced_metrics['accuracy'] - original_metrics['accuracy']
    precision_improvement = enhanced_metrics['precision'] - original_metrics['precision']
    recall_improvement = enhanced_metrics['recall'] - original_metrics['recall']
    f1_improvement = enhanced_metrics['f1_score'] - original_metrics['f1_score']
    
    print(f"{'Accuracy':<15} {original_metrics['accuracy']:<10.3f} {enhanced_metrics['accuracy']:<10.3f} {accuracy_improvement:>+8.3f}")
    print(f"{'Precision':<15} {original_metrics['precision']:<10.3f} {enhanced_metrics['precision']:<10.3f} {precision_improvement:>+8.3f}")
    print(f"{'Recall':<15} {original_metrics['recall']:<10.3f} {enhanced_metrics['recall']:<10.3f} {recall_improvement:>+8.3f}")
    print(f"{'F1 Score':<15} {original_metrics['f1_score']:<10.3f} {enhanced_metrics['f1_score']:<10.3f} {f1_improvement:>+8.3f}")
    
    # Compare confidence
    print(f"\n🎯 CONFIDENCE COMPARISON:")
    print(f"{'Metric':<20} {'Original':<10} {'Enhanced':<10} {'Improvement':<12}")
    print("-" * 55)
    
    avg_conf_improvement = enhanced_confidence['average_confidence'] - original_confidence['average_confidence']
    high_conf_improvement = enhanced_confidence['high_confidence_rate'] - original_confidence['high_confidence_rate']
    
    print(f"{'Avg Confidence':<20} {original_confidence['average_confidence']:<10.3f} {enhanced_confidence['average_confidence']:<10.3f} {avg_conf_improvement:>+8.3f}")
    print(f"{'High Conf Rate':<20} {original_confidence['high_confidence_rate']:<10.3f} {enhanced_confidence['high_confidence_rate']:<10.3f} {high_conf_improvement:>+8.3f}")
    
    # Show detailed predictions
    print(f"\n🔍 DETAILED PREDICTIONS:")
    print(f"{'Text':<40} {'True':<10} {'Original':<10} {'Enhanced':<10}")
    print("-" * 80)
    
    test_data = load_test_data()
    for i, ticket in enumerate(test_data):
        text = ticket['text'][:35] + "..." if len(ticket['text']) > 35 else ticket['text']
        true_cat = ticket['category']
        orig_cat = original_predictions[i]['category']
        enh_cat = enhanced_predictions[i]['category']
        
        orig_mark = "✅" if orig_cat == true_cat else "❌"
        enh_mark = "✅" if enh_cat == true_cat else "❌"
        
        print(f"{text:<40} {true_cat:<10} {orig_cat:<10}{orig_mark} {enh_cat:<10}{enh_mark}")

def test_specific_cases():
    """Test specific challenging cases"""
    print("\n" + "="*60)
    print("SPECIFIC CASE TESTING")
    print("="*60)
    
    from app.models.rule_based_classifier import rule_based_classifier
    from app.models.enhanced_classifier import enhanced_classifier
    
    test_cases = [
        "I was charged $50 extra on my monthly bill",
        "The app keeps crashing when I try to upload files",
        "Can you add support for mobile notifications?",
        "I cannot access my account. It says my password is incorrect.",
        "How do I set up two-factor authentication?",
        "My subscription was renewed but I didn't authorize it.",
        "The search function is not working properly.",
        "Please add integration with Google Calendar.",
        "I'm getting error 404 when trying to access the dashboard.",
        "How do I export my data?"
    ]
    
    print(f"{'Text':<50} {'Original':<15} {'Enhanced':<15}")
    print("-" * 85)
    
    for text in test_cases:
        orig_result = rule_based_classifier.classify_with_confidence_label(text)
        enh_result = enhanced_classifier.classify_with_confidence_label(text)
        
        orig_cat = f"{orig_result['category']} ({orig_result['confidence']:.2f})"
        enh_cat = f"{enh_result['category']} ({enh_result['confidence']:.2f})"
        
        print(f"{text[:45] + '...' if len(text) > 45 else text:<50} {orig_cat:<15} {enh_cat:<15}")

def main():
    """Main test function"""
    print("SUPPORT TICKET CLASSIFIER ACCURACY IMPROVEMENT TEST")
    print("=" * 60)
    
    try:
        # Test original classifier
        original_metrics, original_confidence, original_predictions = test_original_classifier()
        
        # Test enhanced classifier
        enhanced_metrics, enhanced_confidence, enhanced_predictions = test_enhanced_classifier()
        
        # Compare results
        compare_results(original_metrics, original_confidence, original_predictions,
                       enhanced_metrics, enhanced_confidence, enhanced_predictions)
        
        # Test specific cases
        test_specific_cases()
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        accuracy_improvement = enhanced_metrics['accuracy'] - original_metrics['accuracy']
        f1_improvement = enhanced_metrics['f1_score'] - original_metrics['f1_score']
        
        if accuracy_improvement > 0:
            print(f"🎉 ACCURACY IMPROVED by {accuracy_improvement:.1%}")
        else:
            print(f"📉 ACCURACY DECREASED by {abs(accuracy_improvement):.1%}")
        
        if f1_improvement > 0:
            print(f"🎉 F1 SCORE IMPROVED by {f1_improvement:.1%}")
        else:
            print(f"📉 F1 SCORE DECREASED by {abs(f1_improvement):.1%}")
        
        print(f"\nEnhanced classifier achieves {enhanced_metrics['accuracy']:.1%} accuracy")
        print(f"Enhanced classifier achieves {enhanced_metrics['f1_score']:.1%} F1 score")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 