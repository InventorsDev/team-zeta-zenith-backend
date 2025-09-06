import re
import string
import nltk
from typing import List, Optional
import logging

# Download required NLTK data automatically
def download_nltk_resources():
    """Download required NLTK resources"""
    resources = ['punkt', 'stopwords', 'wordnet', 'averaged_perceptron_tagger']
    
    for resource in resources:
        try:
            nltk.data.find(f'tokenizers/{resource}')
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception as e:
                logging.warning(f"Could not download NLTK resource {resource}: {e}")

# Download resources on import
download_nltk_resources()

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

logger = logging.getLogger(__name__)

class TextProcessor:
    """Text preprocessing pipeline for support tickets"""
    
    def __init__(self, remove_stopwords: bool = True, lemmatize: bool = True):
        self.remove_stopwords = remove_stopwords
        self.lemmatize = lemmatize
        
        # Initialize stop words
        try:
            self.stop_words = set(stopwords.words('english')) if remove_stopwords else set()
        except Exception as e:
            logger.warning(f"Could not load stopwords: {e}")
            self.stop_words = set()
        
        # Initialize lemmatizer
        try:
            self.lemmatizer = WordNetLemmatizer() if lemmatize else None
        except Exception as e:
            logger.warning(f"Could not initialize lemmatizer: {e}")
            self.lemmatizer = None
        
        # Common support ticket patterns to clean
        self.ticket_patterns = [
            r'ticket\s*#?\s*\d+',  # Remove ticket numbers
            r'case\s*#?\s*\d+',    # Remove case numbers
            r'ref\s*#?\s*\d+',     # Remove reference numbers
        ]
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove ticket/case numbers
        for pattern in self.ticket_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words using simple whitespace splitting
        Avoids NLTK punkt_tab issues
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        if not text:
            return []
        
        # Use simple whitespace splitting to avoid NLTK issues
        tokens = text.split()
        
        # Remove punctuation from tokens
        tokens = [token for token in tokens if token not in string.punctuation]
        
        return tokens
    
    def remove_stop_words(self, tokens: List[str]) -> List[str]:
        """
        Remove stop words from tokens
        
        Args:
            tokens: List of tokens
            
        Returns:
            Tokens with stop words removed
        """
        if not self.remove_stopwords or not self.stop_words:
            return tokens
        
        return [token for token in tokens if token.lower() not in self.stop_words]
    
    def lemmatize_tokens(self, tokens: List[str]) -> List[str]:
        """
        Lemmatize tokens
        
        Args:
            tokens: List of tokens
            
        Returns:
            Lemmatized tokens
        """
        if not self.lemmatize or not self.lemmatizer:
            return tokens
        
        try:
            return [self.lemmatizer.lemmatize(token) for token in tokens]
        except Exception as e:
            logger.warning(f"Lemmatization failed: {e}")
            return tokens
    
    def preprocess(self, text: str, return_tokens: bool = False) -> str:
        """
        Complete text preprocessing pipeline
        
        Args:
            text: Input text
            return_tokens: Whether to return tokens or joined text
            
        Returns:
            Preprocessed text or tokens
        """
        try:
            # Clean text
            cleaned_text = self.clean_text(text)
            
            # Tokenize
            tokens = self.tokenize(cleaned_text)
            
            # Remove stop words
            tokens = self.remove_stop_words(tokens)
            
            # Lemmatize
            tokens = self.lemmatize_tokens(tokens)
            
            # Filter out empty tokens
            tokens = [token for token in tokens if token.strip()]
            
            if return_tokens:
                return tokens
            else:
                return ' '.join(tokens)
                
        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            return text if not return_tokens else [text]
    
    def batch_preprocess(self, texts: List[str], return_tokens: bool = False) -> List[str]:
        """
        Preprocess multiple texts
        
        Args:
            texts: List of input texts
            return_tokens: Whether to return tokens or joined text
            
        Returns:
            List of preprocessed texts
        """
        return [self.preprocess(text, return_tokens) for text in texts]

# Global text processor instance
text_processor = TextProcessor() 