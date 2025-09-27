import re
from typing import Dict, List, Tuple, Optional
import logging
from collections import Counter
import math

logger = logging.getLogger(__name__)

class EnhancedClassifier:
    """
    Enhanced rule-based classifier with improved accuracy
    Uses advanced pattern matching, context analysis, and weighted scoring
    """
    
    def __init__(self):
        # Enhanced category patterns with more sophisticated rules
        self.category_patterns = {
            'billing': {
                'high_priority_keywords': [
                    'bill', 'billing', 'payment', 'charge', 'cost', 'price', 'fee',
                    'invoice', 'subscription', 'refund', 'credit', 'debit', 'money',
                    'dollar', 'dollars', 'charged', 'charging', 'overcharge'
                ],
                'medium_priority_keywords': [
                    'monthly', 'annual', 'yearly', 'renewal', 'cancel', 'cancellation',
                    'paid', 'unpaid', 'billing cycle', 'payment issue', 'payment problem'
                ],
                'patterns': [
                    r'\$\d+',  # Dollar amounts
                    r'\d+\s*(dollar|dollars)',  # Dollar amounts in words
                    r'(monthly|annual|yearly)\s*(fee|charge|cost)',  # Billing cycles
                    r'(charged|billed)\s+\d+',  # Charged amounts
                    r'payment\s+(issue|problem|error)',  # Payment issues
                    r'(subscription|billing)\s+(renewed|renewal)',  # Subscription renewals
                    r'(refund|credit)\s+(request|issue)',  # Refund requests
                ],
                'negative_patterns': [
                    r'feature.*request',  # Don't confuse with feature requests
                    r'bug.*report',  # Don't confuse with bug reports
                ],
                'weight': 1.3
            },
            'bug': {
                'high_priority_keywords': [
                    'bug', 'error', 'crash', 'broken', 'fail', 'failure',
                    'glitch', 'defect', 'malfunction', 'exception', 'stack trace'
                ],
                'medium_priority_keywords': [
                    'not working', 'doesn\'t work', 'stopped working', 'faulty', 'defective',
                    'crashed', 'crashing', 'freeze', 'frozen', 'hanging', 'slow', 'performance'
                ],
                'patterns': [
                    r'error\s+\d+',  # Error codes
                    r'crash(ed|ing)?',  # Crash variations
                    r'not\s+working',  # Not working
                    r'doesn\'?t\s+work',  # Doesn't work
                    r'keeps?\s+(crashing|freezing|hanging)',  # Continuous issues
                    r'(broken|faulty|defective)',  # Broken items
                    r'performance\s+(issue|problem)',  # Performance issues
                    r'(freeze|frozen|hanging)',  # System freezes
                ],
                'negative_patterns': [
                    r'feature.*request',  # Don't confuse with feature requests
                    r'account.*issue',  # Don't confuse with account issues
                ],
                'weight': 1.4
            },
            'feature': {
                'high_priority_keywords': [
                    'feature', 'request', 'add', 'new', 'enhancement', 'improvement',
                    'suggestion', 'idea', 'proposal', 'missing', 'need', 'want'
                ],
                'medium_priority_keywords': [
                    'would like', 'wish', 'hope', 'could you', 'can you', 'please add',
                    'request', 'asking', 'suggest', 'propose', 'enhance', 'improve'
                ],
                'patterns': [
                    r'feature\s+request',  # Feature request
                    r'add\s+\w+',  # Add something
                    r'new\s+\w+',  # New something
                    r'would\s+like\s+to',  # Would like to
                    r'can\s+you\s+add',  # Can you add
                    r'please\s+add',  # Please add
                    r'request\s+for',  # Request for
                    r'missing\s+\w+',  # Missing something
                    r'need\s+\w+',  # Need something
                ],
                'negative_patterns': [
                    r'bug.*report',  # Don't confuse with bug reports
                    r'account.*issue',  # Don't confuse with account issues
                ],
                'weight': 1.2
            },
            'account': {
                'high_priority_keywords': [
                    'account', 'login', 'password', 'username', 'email', 'sign in',
                    'sign up', 'register', 'registration', 'locked', 'suspended', 'deleted'
                ],
                'medium_priority_keywords': [
                    'profile', 'settings', 'preferences', 'security', 'authentication',
                    'authorization', 'reset', 'change', 'update', 'access', 'cannot access'
                ],
                'patterns': [
                    r'can\'?t\s+login',  # Can't login
                    r'forgot\s+password',  # Forgot password
                    r'reset\s+password',  # Reset password
                    r'account\s+(locked|suspended|deleted)',  # Account status
                    r'cannot\s+access',  # Cannot access
                    r'locked\s+out',  # Locked out
                    r'sign\s+(in|up)',  # Sign in/up
                    r'login\s+(issue|problem)',  # Login issues
                    r'password\s+(reset|change)',  # Password changes
                ],
                'negative_patterns': [
                    r'feature.*request',  # Don't confuse with feature requests
                    r'bug.*report',  # Don't confuse with bug reports
                ],
                'weight': 1.5
            },
            'technical': {
                'high_priority_keywords': [
                    'technical', 'support', 'help', 'assistance', 'guide', 'tutorial',
                    'documentation', 'how to', 'setup', 'configuration', 'install'
                ],
                'medium_priority_keywords': [
                    'installation', 'update', 'upgrade', 'version', 'compatibility',
                    'system', 'platform', 'browser', 'mobile', 'desktop', 'configure'
                ],
                'patterns': [
                    r'how\s+to',  # How to
                    r'setup\s+\w+',  # Setup something
                    r'install(ation)?',  # Install/installation
                    r'update\s+\w+',  # Update something
                    r'configure\s+\w+',  # Configure something
                    r'help\s+with',  # Help with
                    r'two.?factor\s+authentication',  # 2FA
                    r'export\s+\w+',  # Export something
                    r'email\s+settings',  # Email settings
                ],
                'negative_patterns': [
                    r'bug.*report',  # Don't confuse with bug reports
                    r'account.*issue',  # Don't confuse with account issues
                ],
                'weight': 1.1
            }
        }
        
        # Default category for unmatched tickets
        self.default_category = 'general'
        
        # Enhanced confidence thresholds
        self.high_confidence_threshold = 0.7
        self.medium_confidence_threshold = 0.4
        
        # Context words that boost confidence
        self.context_boosters = {
            'billing': ['money', 'payment', 'charge', 'bill', 'cost', 'refund'],
            'bug': ['error', 'crash', 'broken', 'fail', 'issue', 'problem'],
            'feature': ['add', 'new', 'request', 'enhancement', 'improvement'],
            'account': ['login', 'password', 'access', 'account', 'security'],
            'technical': ['help', 'how', 'setup', 'configure', 'install']
        }
    
    def _calculate_keyword_score(self, text: str, keywords: Dict[str, List[str]]) -> float:
        """Calculate enhanced keyword score with priority levels"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        high_matches = 0
        medium_matches = 0
        
        # Count high priority matches
        for keyword in keywords.get('high_priority_keywords', []):
            if keyword.lower() in text_lower:
                high_matches += 1
        
        # Count medium priority matches
        for keyword in keywords.get('medium_priority_keywords', []):
            if keyword.lower() in text_lower:
                medium_matches += 1
        
        # Weighted scoring: high priority matches count more
        total_score = (high_matches * 2.0) + (medium_matches * 1.0)
        total_keywords = len(keywords.get('high_priority_keywords', [])) + len(keywords.get('medium_priority_keywords', []))
        
        # Normalize and boost for multiple matches
        base_score = total_score / total_keywords if total_keywords > 0 else 0.0
        
        # Boost for multiple matches
        if high_matches + medium_matches > 1:
            base_score *= (1 + 0.3 * (high_matches + medium_matches))
        
        return min(base_score, 1.0)
    
    def _calculate_pattern_score(self, text: str, patterns: List[str], negative_patterns: List[str] = None) -> float:
        """Calculate enhanced pattern score with negative patterns"""
        if not text:
            return 0.0
        
        positive_matches = 0
        negative_matches = 0
        
        # Count positive pattern matches
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                positive_matches += 1
        
        # Count negative pattern matches (penalize)
        if negative_patterns:
            for pattern in negative_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    negative_matches += 1
        
        # Calculate base score
        total_patterns = len(patterns)
        base_score = positive_matches / total_patterns if total_patterns > 0 else 0.0
        
        # Boost for pattern matches
        if positive_matches > 0:
            base_score *= 1.5
        
        # Penalize for negative matches
        if negative_matches > 0:
            base_score *= 0.5
        
        return min(base_score, 1.0)
    
    def _calculate_context_score(self, text: str, category: str) -> float:
        """Calculate context score based on surrounding words"""
        if category not in self.context_boosters:
            return 0.0
        
        text_lower = text.lower()
        context_words = self.context_boosters[category]
        
        # Count context word occurrences
        context_matches = sum(1 for word in context_words if word in text_lower)
        
        # Normalize by text length and context word count
        text_words = len(text.split())
        if text_words == 0:
            return 0.0
        
        context_density = context_matches / text_words
        return min(context_density * 2, 0.3)  # Cap at 0.3
    
    def _calculate_category_score(self, text: str, category: str) -> float:
        """Calculate comprehensive category score"""
        if category not in self.category_patterns:
            return 0.0
        
        patterns = self.category_patterns[category]
        
        # Calculate keyword score (weight: 0.5)
        keyword_score = self._calculate_keyword_score(text, patterns)
        
        # Calculate pattern score (weight: 0.4)
        pattern_score = self._calculate_pattern_score(
            text, 
            patterns['patterns'], 
            patterns.get('negative_patterns', [])
        )
        
        # Calculate context score (weight: 0.1)
        context_score = self._calculate_context_score(text, category)
        
        # Weighted combination
        total_score = (0.5 * keyword_score) + (0.4 * pattern_score) + (0.1 * context_score)
        
        # Apply category weight
        category_weight = patterns.get('weight', 1.0)
        total_score *= category_weight
        
        return min(total_score, 1.0)
    
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify a support ticket with enhanced accuracy
        
        Args:
            text: Input ticket text
            
        Returns:
            Tuple of (category, confidence_score)
        """
        if not text or not isinstance(text, str):
            return self.default_category, 0.0
        
        # Calculate scores for all categories
        category_scores = {}
        for category in self.category_patterns.keys():
            score = self._calculate_category_score(text, category)
            category_scores[category] = score
        
        # Find the category with highest score
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            best_score = category_scores[best_category]
            
            # If best score is too low, use default category
            if best_score < 0.15:
                return self.default_category, 0.15
            
            return best_category, min(best_score, 1.0)
        
        return self.default_category, 0.15
    
    def classify_with_confidence_label(self, text: str) -> Dict[str, any]:
        """
        Classify with detailed confidence information
        
        Args:
            text: Input ticket text
            
        Returns:
            Dictionary with category, confidence score, and confidence label
        """
        category, confidence = self.classify(text)
        
        # Determine confidence label
        if confidence >= self.high_confidence_threshold:
            confidence_label = "high"
        elif confidence >= self.medium_confidence_threshold:
            confidence_label = "medium"
        else:
            confidence_label = "low"
        
        return {
            "category": category,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "text": text
        }
    
    def batch_classify(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Classify multiple tickets
        
        Args:
            texts: List of ticket texts
            
        Returns:
            List of classification results
        """
        return [self.classify_with_confidence_label(text) for text in texts]
    
    def get_supported_categories(self) -> List[str]:
        """Get list of supported categories"""
        return list(self.category_patterns.keys()) + [self.default_category]

# Global enhanced classifier instance
enhanced_classifier = EnhancedClassifier() 