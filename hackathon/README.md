# Support Ticket Analysis ML System

A comprehensive **ML-powered support ticket analysis system** with
classification, sentiment analysis, trend detection, anomaly detection,
and monitoring capabilities.

🚀 **Current Status: Sprint 3 Complete**

------------------------------------------------------------------------

## ✅ Sprint Progress

### Sprint 1 - Foundation & Core Infrastructure

-   ML environment setup with required libraries\
-   Text preprocessing pipeline (cleaning, tokenization, lemmatization)\
-   Rule-based classifier for 5+ categories\
-   Classification confidence scoring\
-   Sentiment analysis using VADER\
-   FastAPI endpoints for real-time inference\
-   Model evaluation framework\
-   Improved classifier with **93.3% accuracy**

### Sprint 2 - ML Integrations & Data Pipeline

-   BERT-based classification with fine-tuning\
-   Trend detection for categories and sentiment\
-   Anomaly detection for unusual patterns\
-   Model monitoring and performance tracking\
-   Automated retraining triggers\
-   Model versioning and rollback capability\
-   A/B testing framework for model comparison

### Sprint 3 - Advanced Analytics & Monitoring

-   Ticket similarity detection and clustering\
-   Predictive models for ticket volume and trends\
-   ML model optimization for production performance\
-   Slack integration for alerts and notifications

------------------------------------------------------------------------

## 🎯 Key Features

### Classification Systems

-   **Improved Classifier** → 93.3% accuracy (trained on
    expanded_tickets.json)\
-   **BERT Classifier** → Transformer-based classification with
    fine-tuning\
-   **Rule-based Classifier** → Fast fallback system with predefined
    patterns\
-   **Automatic Fallback** → Seamless switching between classifiers

### Analytics & Monitoring

-   **Trend Detection** → Volume and sentiment analysis over time\
-   **Anomaly Detection** → Pattern anomaly detection with alerting\
-   **Model Monitoring** → Real-time performance tracking and drift
    detection\
-   **Automated Retraining** → Smart triggers for retraining models

### API Endpoints

  Endpoint                              Description
  ------------------------------------- ------------------------------
  `POST /api/v1/ml/classify`            Main classification endpoint
  `POST /api/v1/ml/classify/bert`       BERT-based classification
  `POST /api/v1/ml/classify/improved`   Improved classifier only
  `POST /api/v1/ml/sentiment`           Sentiment analysis
  `POST /api/v1/ml/batch`               Batch processing
  `POST /api/v1/ml/trends/volume`       Volume trend analysis
  `POST /api/v1/ml/trends/sentiment`    Sentiment trend analysis
  `POST /api/v1/ml/trends/anomalies`    Anomaly detection
  `GET /api/v1/ml/monitoring/health`    Model health dashboard
  `POST /api/v1/ml/bert/train`          BERT model training

------------------------------------------------------------------------

## 🛠 Quick Start

### 1. Install Dependencies

``` bash
pip install -r requirements.txt
```

### 2. Start the API Server

``` bash
uvicorn app.main:app --reload
```

### 3. Test the System

``` bash
# Test Sprint 1 features
python test_system.py

# Test Sprint 2 features
python test_sprint2.py

# Test Sprint 3 features
python test_sprint3.py
```

### 4. API Examples

**Classify a Ticket**

``` bash
curl -X POST "http://localhost:8000/api/v1/ml/classify"   -H "Content-Type: application/json"   -d '{"text": "I was charged $50 extra on my bill"}'
```

**Analyze Sentiment**

``` bash
curl -X POST "http://localhost:8000/api/v1/ml/sentiment"   -H "Content-Type: application/json"   -d '{"text": "I love this product! It's amazing!"}'
```

**Get Model Health**

``` bash
curl -X GET "http://localhost:8000/api/v1/ml/monitoring/health"
```

------------------------------------------------------------------------

## 📊 Performance Metrics

### Classification Accuracy

-   **Improved Classifier** → 93.3% accuracy\
-   **Rule-based Classifier** → 60% accuracy\
-   **BERT Classifier** → Ready for fine-tuning

### Model Health

-   Real-time performance monitoring\
-   Drift detection with automated alerts\
-   Confidence score tracking\
-   Automated retraining triggers

------------------------------------------------------------------------

## 🏗 Project Structure

    hackathon/
    ├── app/
    │   ├── api/
    │   │   └── ml_endpoints.py          # FastAPI endpoints
    │   ├── models/
    │   │   ├── rule_based_classifier.py # Rule-based classifier
    │   │   ├── improved_classifier.py   # Improved classifier (93.3% accuracy)
    │   │   ├── bert_classifier.py       # BERT-based classifier
    │   │   ├── sentiment_analyzer.py    # Sentiment analysis
    │   │   └── evaluation.py            # Model evaluation
    │   ├── preprocessing/
    │   │   └── text_processor.py        # Text preprocessing
    │   ├── analytics/
    │   │   ├── trend_detector.py        # Trend detection & anomalies
    │   │   ├── anomaly_detector.py      # Anomaly detection module
    │   │   └── similarity_detector.py   # Similarity detection (Sprint 3)
    │   ├── monitoring/
    │   │   ├── model_monitor.py         # Model monitoring & drift detection
    │   │   └── slack_notifier.py        # Slack notifications for alerts
    │   ├── utils/
    │   │   └── logging.py               # Logging configuration
    │   └── main.py                      # FastAPI application
    ├── data/
    │   ├── sample_tickets.json          # Sample test data
    │   ├── expanded_tickets.json        # Sprint 1 & 3 dataset
    │   └── dataset-tickets-multi-lang3-4k.csv           # Sprint 2 dataset
    ├── notebooks/
    │   ├── sprint1_foundation.ipynb     # Sprint 1 notebook
    │   ├── sprint2_trends.ipynb         # Sprint 2 notebook
    │   └── sprint3_similarity_forecasting.ipynb      # Sprint 3 notebook
    ├── models/                          # Saved model files
    ├── logs/                            # Application logs
    ├── requirements.txt                 # Python dependencies
    ├── test_system.py                   # Sprint 1 tests
    ├── test_sprint2.py                  # Sprint 2 tests
    ├── test_sprint3.py                  # Sprint 3 tests
    └── README.md                        # Project documentation

------------------------------------------------------------------------

## 🔧 Configuration

### Environment Variables

-   `LOG_LEVEL` → Logging level (default: INFO)\
-   `MODEL_PATH` → Path to saved models (default: models/)\
-   `SLACK_WEBHOOK_URL` → Webhook URL for Slack alerts

### Model Settings

-   **Improved Classifier** → Learns from `expanded_tickets.json`\
-   **BERT Classifier** → Configurable epochs, batch size, learning
    rate\
-   **Monitoring** → Configurable thresholds for drift detection

------------------------------------------------------------------------

## 📈 Sprint 3 Achievements

-   ✅ Ticket similarity detection using embeddings\
-   ✅ Clustering for related tickets\
-   ✅ Predictive models for ticket volume trends\
-   ✅ Optimized inference for performance\
-   ✅ Slack alerts for monitoring & anomaly detection

------------------------------------------------------------------------

## 🤝 Contributing

This is a hackathon project demonstrating ML-powered support ticket
analysis.\
The system is designed to be **extensible and production-ready**.

------------------------------------------------------------------------

## 📄 License

This project is part of a hackathon demonstration.
