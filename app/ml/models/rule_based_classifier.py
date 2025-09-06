import re
from typing import Dict, List, Tuple, Optional
import logging
from collections import Counter

logger = logging.getLogger(__name__)

class RuleBasedClassifier:
    """
    Rule-based classifier for support ticket categorization
    Supports: billing, bug, feature, account, general, technical
    """
    
    def __init__(self):
        # Define category keywords and patterns with improved scoring
        self.category_patterns = {
            'billing': {
                'keywords': [
                    'bill', 'billing', 'payment', 'charge', 'cost', 'price', 'fee',
                    'invoice', 'subscription', 'refund', 'credit', 'debit', 'money',
                    'dollar', 'dollars', 'paid', 'unpaid', 'overcharge', 'billing cycle',
                    'monthly', 'annual', 'yearly', 'renewal', 'cancel', 'cancellation',
                    'charged', 'charging', 'payment', 'pay', 'paid', 'unpaid'
                ],
                'patterns': [
                    r'\$\d+',  # Dollar amounts
                    r'\d+\s*(dollar|dollars)',  # Dollar amounts in words
                    r'(monthly|annual|yearly)\s*(fee|charge|cost)',  # Billing cycles
                    r'(charged|billed)\s+\d+',  # Charged amounts
                    r'payment\s+(issue|problem|error)',  # Payment issues
                ],
                'weight': 1.2  # Higher weight for billing
            },
            'bug': {
                'keywords': [
                    'bug', 'error', 'crash', 'broken', 'not working', 'fail', 'failure',
                    'issue', 'problem', 'glitch', 'defect', 'malfunction', 'doesn\'t work',
                    'stopped working', 'broken', 'faulty', 'defective', 'error message',
                    'exception', 'stack trace', 'debug', 'debugging', 'crashed', 'crashing',
                    'freeze', 'frozen', 'hanging', 'slow', 'performance', 'broken'
                ],
                'patterns': [
                    r'error\s+\d+',  # Error codes
                    r'crash(ed|ing)?',  # Crash variations
                    r'not\s+working',  # Not working
                    r'doesn\'?t\s+work',  # Doesn't work
                    r'keeps?\s+(crashing|freezing|hanging)',  # Continuous issues
                    r'(broken|faulty|defective)',  # Broken items
                ],
                'weight': 1.3  # High weight for bugs
            },
            'feature': {
                'keywords': [
                    'feature', 'request', 'add', 'new', 'enhancement', 'improvement',
                    'suggestion', 'idea', 'proposal', 'would like', 'wish', 'hope',
                    'could you', 'can you', 'please add', 'missing', 'need', 'want',
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
                ],
                'weight': 1.1  # Medium weight for features
            },
            'account': {
                'keywords': [
                    'account', 'login', 'password', 'username', 'email', 'sign in',
                    'sign up', 'register', 'registration', 'profile', 'settings',
                    'preferences', 'security', 'authentication', 'authorization',
                    'locked', 'suspended', 'deleted', 'reset', 'change', 'update',
                    'access', 'cannot access', 'locked out', 'forgot password'
                ],
                'patterns': [
                    r'can\'?t\s+login',  # Can't login
                    r'forgot\s+password',  # Forgot password
                    r'reset\s+password',  # Reset password
                    r'account\s+(locked|suspended|deleted)',  # Account status
                    r'cannot\s+access',  # Cannot access
                    r'locked\s+out',  # Locked out
                ],
                'weight': 1.4  # High weight for account issues
            },
            'technical': {
                'keywords': [
                    'technical', 'support', 'help', 'assistance', 'guide', 'tutorial',
                    'documentation', 'how to', 'setup', 'configuration', 'install',
                    'installation', 'update', 'upgrade', 'version', 'compatibility',
                    'system', 'platform', 'browser', 'mobile', 'desktop', 'configure',
                    'setup', 'install', 'update', 'upgrade', 'how do i'
                ],
                'patterns': [
                    r'how\s+to',  # How to
                    r'setup\s+\w+',  # Setup something
                    r'install(ation)?',  # Install/installation
                    r'update\s+\w+',  # Update something
                    r'configure\s+\w+',  # Configure something
                    r'help\s+with',  # Help with
                ],
                'weight': 1.0  # Standard weight for technical
            }
        }
        
        # Default category for unmatched tickets
        self.default_category = 'general'
        
        # Confidence thresholds
        self.high_confidence_threshold = 0.6
        self.medium_confidence_threshold = 0.3
    
    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> float:
        """Calculate score based on keyword matches with improved scoring"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        matches = 0
        total_keywords = len(keywords)
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matches += 1
        
        # Normalize by number of keywords, but boost for multiple matches
        base_score = matches / total_keywords if total_keywords > 0 else 0.0
        
        # Boost score for multiple matches
        if matches > 1:
            base_score *= (1 + 0.2 * matches)
        
        return min(base_score, 1.0)
    
    def _calculate_pattern_score(self, text: str, patterns: List[str]) -> float:
        """Calculate score based on regex pattern matches"""
        if not text:
            return 0.0
        
        matches = 0
        total_patterns = len(patterns)
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        # Pattern matches are more significant than keyword matches
        base_score = matches / total_patterns if total_patterns > 0 else 0.0
        
        # Boost for pattern matches
        if matches > 0:
            base_score *= 1.5
        
        return min(base_score, 1.0)
    
    def _calculate_category_score(self, text: str, category: str) -> float:
        """Calculate overall score for a category with weights"""
        if category not in self.category_patterns:
            return 0.0
        
        patterns = self.category_patterns[category]
        
        # Calculate keyword score (weight: 0.6)
        keyword_score = self._calculate_keyword_score(text, patterns['keywords'])
        
        # Calculate pattern score (weight: 0.4)
        pattern_score = self._calculate_pattern_score(text, patterns['patterns'])
        
        # Weighted combination
        total_score = (0.6 * keyword_score) + (0.4 * pattern_score)
        
        # Apply category weight
        category_weight = patterns.get('weight', 1.0)
        total_score *= category_weight
        
        return min(total_score, 1.0)
    
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify a support ticket
        
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
            if best_score < 0.1:
                return self.default_category, 0.1
            
            return best_category, min(best_score, 1.0)
        
        return self.default_category, 0.1
    
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

# Global classifier instance
rule_based_classifier = RuleBasedClassifier() 