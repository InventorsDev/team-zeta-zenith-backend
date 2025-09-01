#!/usr/bin/env python3
"""
Download NLTK resources for Support Ticket Analysis ML System
"""

import nltk
import sys

def download_nltk_resources():
    """Download all required NLTK resources"""
    print("Downloading NLTK resources...")
    
    resources = [
        'punkt',
        'stopwords', 
        'wordnet',
        'averaged_perceptron_tagger',
        'omw-1.4'  # Open Multilingual Wordnet
    ]
    
    for resource in resources:
        try:
            print(f"Downloading {resource}...")
            nltk.download(resource, quiet=False)
            print(f"✅ {resource} downloaded successfully")
        except Exception as e:
            print(f"❌ Failed to download {resource}: {e}")
    
    print("\nNLTK resources download completed!")

def test_nltk_imports():
    """Test if NLTK resources are working"""
    print("\nTesting NLTK imports...")
    
    try:
        from nltk.tokenize import word_tokenize
        test_text = "This is a test sentence."
        tokens = word_tokenize(test_text)
        print(f"✅ Tokenization working: {tokens}")
    except Exception as e:
        print(f"❌ Tokenization failed: {e}")
    
    try:
        from nltk.corpus import stopwords
        stops = stopwords.words('english')
        print(f"✅ Stopwords loaded: {len(stops)} words")
    except Exception as e:
        print(f"❌ Stopwords failed: {e}")
    
    try:
        from nltk.stem import WordNetLemmatizer
        lemmatizer = WordNetLemmatizer()
        result = lemmatizer.lemmatize("running")
        print(f"✅ Lemmatization working: running -> {result}")
    except Exception as e:
        print(f"❌ Lemmatization failed: {e}")

def main():
    print("NLTK Resource Downloader")
    print("=" * 40)
    
    download_nltk_resources()
    test_nltk_imports()
    
    print("\n🎉 NLTK setup completed!")
    print("You can now run the tests without NLTK errors.")

if __name__ == "__main__":
    main() 