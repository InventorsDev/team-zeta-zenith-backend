#!/usr/bin/env python3
"""
Comprehensive accuracy test comparing original, enhanced, and improved classifiers
"""

import json
import time
from typing import List, Dict, Any

def load_test_data():
    """Load test data from sample tickets"""
    with open('data/sample_tickets.json', 'r') as f:
        return json.load(f)

def test_classifier(classifier_name: str, classifier_instance):
    """Test a specific classifier"""
    print(f"Testing {classifier_name}...")
    
    from app.models.evaluation import model_evaluator
    
    # Load test data
    test_data = load_test_data()
    
    # Prepare test data
    y_true = [ticket['category'] for ticket in test_data]
    y_pred = []
    predictions = []
    
    start_time = time.time()
    
    for ticket in test_data:
        result = classifier_instance.classify_with_confidence_label(ticket['text'])
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

def main():
    """Main test function"""
    print("COMPREHENSIVE CLASSIFIER ACCURACY COMPARISON")
    print("=" * 60)
    
    try:
        # Test original classifier
        from app.models.rule_based_classifier import rule_based_classifier
        original_metrics, original_confidence, original_predictions = test_classifier(
            "Original Classifier", rule_based_classifier
        )
        
        # Test enhanced classifier
        from app.models.enhanced_classifier import enhanced_classifier
        enhanced_metrics, enhanced_confidence, enhanced_predictions = test_classifier(
            "Enhanced Classifier", enhanced_classifier
        )
        
        # Test improved classifier
        from app.models.improved_classifier import improved_classifier
        improved_metrics, improved_confidence, improved_predictions = test_classifier(
            "Improved Classifier", improved_classifier
        )
        
        # Show training stats for improved classifier
        print(f"\n📊 TRAINING STATISTICS:")
        training_stats = improved_classifier.get_training_stats()
        print(f"Total training tickets: {training_stats['total_tickets']}")
        print(f"Category distribution: {training_stats['category_distribution']}")
        
        # Compare all results
        print("\n" + "="*60)
        print("COMPREHENSIVE COMPARISON RESULTS")
        print("="*60)
        
        # Compare metrics
        print("\n📊 METRICS COMPARISON:")
        print(f"{'Metric':<15} {'Original':<10} {'Enhanced':<10} {'Improved':<10} {'Best':<10}")
        print("-" * 60)
        
        classifiers = [
            ("Original", original_metrics),
            ("Enhanced", enhanced_metrics),
            ("Improved", improved_metrics)
        ]
        
        # Find best scores
        best_accuracy = max(metrics['accuracy'] for _, metrics in classifiers)
        best_precision = max(metrics['precision'] for _, metrics in classifiers)
        best_recall = max(metrics['recall'] for _, metrics in classifiers)
        best_f1 = max(metrics['f1_score'] for _, metrics in classifiers)
        
        print(f"{'Accuracy':<15} {original_metrics['accuracy']:<10.3f} {enhanced_metrics['accuracy']:<10.3f} {improved_metrics['accuracy']:<10.3f} {best_accuracy:<10.3f}")
        print(f"{'Precision':<15} {original_metrics['precision']:<10.3f} {enhanced_metrics['precision']:<10.3f} {improved_metrics['precision']:<10.3f} {best_precision:<10.3f}")
        print(f"{'Recall':<15} {original_metrics['recall']:<10.3f} {enhanced_metrics['recall']:<10.3f} {improved_metrics['recall']:<10.3f} {best_recall:<10.3f}")
        print(f"{'F1 Score':<15} {original_metrics['f1_score']:<10.3f} {enhanced_metrics['f1_score']:<10.3f} {improved_metrics['f1_score']:<10.3f} {best_f1:<10.3f}")
        
        # Compare confidence
        print(f"\n🎯 CONFIDENCE COMPARISON:")
        print(f"{'Metric':<20} {'Original':<10} {'Enhanced':<10} {'Improved':<10}")
        print("-" * 55)
        
        print(f"{'Avg Confidence':<20} {original_confidence['average_confidence']:<10.3f} {enhanced_confidence['average_confidence']:<10.3f} {improved_confidence['average_confidence']:<10.3f}")
        print(f"{'High Conf Rate':<20} {original_confidence['high_confidence_rate']:<10.3f} {enhanced_confidence['high_confidence_rate']:<10.3f} {improved_confidence['high_confidence_rate']:<10.3f}")
        
        # Show detailed predictions
        print(f"\n🔍 DETAILED PREDICTIONS:")
        print(f"{'Text':<30} {'True':<8} {'Original':<8} {'Enhanced':<8} {'Improved':<8}")
        print("-" * 70)
        
        test_data = load_test_data()
        for i, ticket in enumerate(test_data):
            text = ticket['text'][:25] + "..." if len(ticket['text']) > 25 else ticket['text']
            true_cat = ticket['category']
            orig_cat = original_predictions[i]['category']
            enh_cat = enhanced_predictions[i]['category']
            imp_cat = improved_predictions[i]['category']
            
            orig_mark = "✅" if orig_cat == true_cat else "❌"
            enh_mark = "✅" if enh_cat == true_cat else "❌"
            imp_mark = "✅" if imp_cat == true_cat else "❌"
            
            print(f"{text:<30} {true_cat:<8} {orig_cat:<8}{orig_mark} {enh_cat:<8}{enh_mark} {imp_cat:<8}{imp_mark}")
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        # Calculate improvements
        orig_to_enh_acc = enhanced_metrics['accuracy'] - original_metrics['accuracy']
        orig_to_imp_acc = improved_metrics['accuracy'] - original_metrics['accuracy']
        orig_to_enh_f1 = enhanced_metrics['f1_score'] - original_metrics['f1_score']
        orig_to_imp_f1 = improved_metrics['f1_score'] - original_metrics['f1_score']
        
        print(f"Original → Enhanced Accuracy: {orig_to_enh_acc:>+6.1%}")
        print(f"Original → Improved Accuracy: {orig_to_imp_acc:>+6.1%}")
        print(f"Original → Enhanced F1: {orig_to_enh_f1:>+6.1%}")
        print(f"Original → Improved F1: {orig_to_imp_f1:>+6.1%}")
        
        # Find best classifier
        best_classifier = max(classifiers, key=lambda x: x[1]['accuracy'])
        print(f"\n🏆 BEST CLASSIFIER: {best_classifier[0]} ({best_classifier[1]['accuracy']:.1%} accuracy)")
        
        if improved_metrics['accuracy'] > original_metrics['accuracy']:
            print("🎉 Improved classifier shows better accuracy!")
        else:
            print("📊 All classifiers perform similarly on this dataset.")
        
        print(f"\n💡 RECOMMENDATION: Use the {best_classifier[0]} classifier for production.")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 