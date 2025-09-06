import re
import json
from typing import Dict, List, Tuple, Optional
import logging
from collections import Counter, defaultdict
import math

logger = logging.getLogger(__name__)

class ImprovedClassifier:
    """
    Improved classifier that learns from training data and uses advanced pattern matching
    """
    
    def __init__(self, training_data_path: str = "data/expanded_tickets.json"):
        self.training_data_path = training_data_path
        self.category_patterns = {}
        self.category_keywords = defaultdict(list)
        self.category_weights = {}
        self.trained = False
        
        # Load and train the classifier
        self._load_training_data()
        self._extract_patterns()
        self._calculate_weights()
        
        # Default category for unmatched tickets
        self.default_category = 'general'
        
        # Confidence thresholds
        self.high_confidence_threshold = 0.7
        self.medium_confidence_threshold = 0.4
    
    def _load_training_data(self):
        """Load training data from JSON file"""
        try:
            with open(self.training_data_path, 'r') as f:
                self.training_data = json.load(f)
            logger.info(f"Loaded {len(self.training_data)} training examples")
        except Exception as e:
            logger.error(f"Failed to load training data: {e}")
            self.training_data = []
    
    def _extract_patterns(self):
        """Extract patterns from training data"""
        # Group tickets by category
        category_tickets = defaultdict(list)
        for ticket in self.training_data:
            category_tickets[ticket['category']].append(ticket['text'])
        
        # Extract patterns for each category
        for category, tickets in category_tickets.items():
            self._extract_category_patterns(category, tickets)
    
    def _extract_category_patterns(self, category: str, tickets: List[str]):
        """Extract patterns for a specific category"""
        # Common patterns for each category
        base_patterns = {
            'billing': [
                r'\$\d+',  # Dollar amounts
                r'\d+\s*(dollar|dollars)',  # Dollar amounts in words
                r'(monthly|annual|yearly)\s*(fee|charge|cost)',  # Billing cycles
                r'(charged|billed)\s+\d+',  # Charged amounts
                r'payment\s+(issue|problem|error)',  # Payment issues
                r'(subscription|billing)\s+(renewed|renewal)',  # Subscription renewals
                r'(refund|credit)\s+(request|issue)',  # Refund requests
                r'overcharge',  # Overcharge
                r'unauthorized\s+charge',  # Unauthorized charges
                r'billing\s+cycle',  # Billing cycle
                r'monthly\s+fee',  # Monthly fee
            ],
            'bug': [
                r'error\s+\d+',  # Error codes
                r'crash(ed|ing)?',  # Crash variations
                r'not\s+working',  # Not working
                r'doesn\'?t\s+work',  # Doesn't work
                r'keeps?\s+(crashing|freezing|hanging)',  # Continuous issues
                r'(broken|faulty|defective)',  # Broken items
                r'performance\s+(issue|problem)',  # Performance issues
                r'(freeze|frozen|hanging)',  # System freezes
                r'timing\s+out',  # Timeout issues
                r'connection\s+(issue|problem)',  # Connection issues
                r'startup\s+(issue|problem)',  # Startup issues
            ],
            'feature': [
                r'feature\s+request',  # Feature request
                r'add\s+\w+',  # Add something
                r'new\s+\w+',  # New something
                r'would\s+like\s+to',  # Would like to
                r'can\s+you\s+add',  # Can you add
                r'please\s+add',  # Please add
                r'request\s+for',  # Request for
                r'missing\s+\w+',  # Missing something
                r'need\s+\w+',  # Need something
                r'suggest\s+adding',  # Suggest adding
                r'consider\s+adding',  # Consider adding
            ],
            'account': [
                r'can\'?t\s+login',  # Can't login
                r'forgot\s+password',  # Forgot password
                r'reset\s+password',  # Reset password
                r'account\s+(locked|suspended|deleted)',  # Account status
                r'cannot\s+access',  # Cannot access
                r'locked\s+out',  # Locked out
                r'sign\s+(in|up)',  # Sign in/up
                r'login\s+(issue|problem)',  # Login issues
                r'password\s+(reset|change)',  # Password changes
                r'username\s+(forgot|remember)',  # Username issues
                r'account\s+(deleted|removed)',  # Account deletion
            ],
            'technical': [
                r'how\s+to',  # How to
                r'setup\s+\w+',  # Setup something
                r'install(ation)?',  # Install/installation
                r'update\s+\w+',  # Update something
                r'configure\s+\w+',  # Configure something
                r'help\s+with',  # Help with
                r'two.?factor\s+authentication',  # 2FA
                r'export\s+\w+',  # Export something
                r'email\s+settings',  # Email settings
                r'notification\s+settings',  # Notification settings
                r'profile\s+setup',  # Profile setup
            ]
        }
        
        # Extract keywords from training data
        keywords = self._extract_keywords_from_tickets(tickets)
        
        # Store patterns and keywords
        self.category_patterns[category] = {
            'patterns': base_patterns.get(category, []),
            'keywords': keywords,
            'negative_patterns': self._get_negative_patterns(category)
        }
        
        # Store keywords separately for quick access
        self.category_keywords[category] = keywords
    
    def _extract_keywords_from_tickets(self, tickets: List[str]) -> List[str]:
        """Extract important keywords from tickets"""
        # Common stop words to exclude
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours',
            'his', 'hers', 'ours', 'theirs', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'shall'
        }
        
        # Count word frequencies
        word_counts = Counter()
        for ticket in tickets:
            # Clean and tokenize
            words = re.findall(r'\b\w+\b', ticket.lower())
            # Filter out stop words and short words
            words = [word for word in words if word not in stop_words and len(word) > 2]
            word_counts.update(words)
        
        # Return top keywords (frequency > 1)
        keywords = [word for word, count in word_counts.most_common(20) if count > 1]
        return keywords
    
    def _get_negative_patterns(self, category: str) -> List[str]:
        """Get negative patterns to avoid false positives"""
        negative_patterns = {
            'billing': [
                r'feature.*request',
                r'bug.*report',
                r'account.*issue'
            ],
            'bug': [
                r'feature.*request',
                r'account.*issue',
                r'billing.*issue'
            ],
            'feature': [
                r'bug.*report',
                r'account.*issue',
                r'billing.*issue'
            ],
            'account': [
                r'feature.*request',
                r'bug.*report',
                r'billing.*issue'
            ],
            'technical': [
                r'bug.*report',
                r'account.*issue',
                r'billing.*issue'
            ]
        }
        return negative_patterns.get(category, [])
    
    def _calculate_weights(self):
        """Calculate category weights based on training data distribution"""
        category_counts = Counter(ticket['category'] for ticket in self.training_data)
        total_tickets = len(self.training_data)
        
        for category, count in category_counts.items():
            # Inverse frequency weighting (less common categories get higher weight)
            frequency = count / total_tickets
            self.category_weights[category] = 1.0 / (frequency + 0.1)  # Add small constant to avoid division by zero
    
    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> float:
        """Calculate keyword match score"""
        if not text or not keywords:
            return 0.0
        
        text_lower = text.lower()
        matches = sum(1 for keyword in keywords if keyword in text_lower)
        
        # Normalize by number of keywords
        base_score = matches / len(keywords) if keywords else 0.0
        
        # Boost for multiple matches
        if matches > 1:
            base_score *= (1 + 0.2 * matches)
        
        return min(base_score, 1.0)
    
    def _calculate_pattern_score(self, text: str, patterns: List[str], negative_patterns: List[str] = None) -> float:
        """Calculate pattern match score with negative patterns"""
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
    
    def _calculate_category_score(self, text: str, category: str) -> float:
        """Calculate comprehensive category score"""
        if category not in self.category_patterns:
            return 0.0
        
        patterns = self.category_patterns[category]
        
        # Calculate keyword score (weight: 0.6)
        keyword_score = self._calculate_keyword_score(text, patterns['keywords'])
        
        # Calculate pattern score (weight: 0.4)
        pattern_score = self._calculate_pattern_score(
            text, 
            patterns['patterns'], 
            patterns.get('negative_patterns', [])
        )
        
        # Weighted combination
        total_score = (0.6 * keyword_score) + (0.4 * pattern_score)
        
        # Apply category weight
        category_weight = self.category_weights.get(category, 1.0)
        total_score *= category_weight
        
        return min(total_score, 1.0)
    
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify a support ticket with improved accuracy
        
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
    
    def get_training_stats(self) -> Dict[str, any]:
        """Get training statistics"""
        category_counts = Counter(ticket['category'] for ticket in self.training_data)
        return {
            "total_tickets": len(self.training_data),
            "category_distribution": dict(category_counts),
            "categories": list(category_counts.keys())
        }

# Global improved classifier instance
improved_classifier = ImprovedClassifier() 