import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from torch.utils.data import Dataset, DataLoader
import numpy as np
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from sklearn.model_selection import train_test_split
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class TicketDataset(Dataset):
    """Custom dataset for support ticket classification"""
    
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        
        # Create label mapping
        self.label2id = {label: idx for idx, label in enumerate(sorted(set(labels)))}
        self.id2label = {idx: label for label, idx in self.label2id.items()}
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        # Tokenize text
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(self.label2id[label], dtype=torch.long)
        }

class BERTClassifier:
    """
    BERT-based classifier for support ticket categorization
    Supports fine-tuning and model versioning
    """
    
    def __init__(self, model_name: str = "bert-base-uncased", max_length: int = 128):
        self.model_name = model_name
        self.max_length = max_length
        self.tokenizer = None
        self.model = None
        self.label2id = {}
        self.id2label = {}
        self.model_version = None
        self.training_history = []
        
        # Model paths
        self.models_dir = "models/bert"
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Initialize tokenizer
        self._load_tokenizer()
    
    def _load_tokenizer(self):
        """Load BERT tokenizer"""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            logger.info(f"Loaded tokenizer: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {e}")
            raise
    
    def _load_model(self, model_path: str = None):
        """Load BERT model"""
        try:
            if model_path and os.path.exists(model_path):
                # Load fine-tuned model
                self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
                # Load label mappings
                with open(os.path.join(model_path, "label_mapping.json"), "r") as f:
                    mapping = json.load(f)
                    self.label2id = mapping["label2id"]
                    self.id2label = mapping["id2label"]
                logger.info(f"Loaded fine-tuned model from: {model_path}")
            else:
                # Load base model
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_name,
                    num_labels=len(self.label2id) if self.label2id else 6
                )
                logger.info(f"Loaded base model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def prepare_data(self, training_data_path: str = "data/expanded_tickets.json"):
        """Prepare training data for BERT fine-tuning"""
        try:
            with open(training_data_path, 'r') as f:
                data = json.load(f)
            
            texts = [item['text'] for item in data]
            labels = [item['category'] for item in data]
            
            # Create label mappings
            unique_labels = sorted(set(labels))
            self.label2id = {label: idx for idx, label in enumerate(unique_labels)}
            self.id2label = {idx: label for label, idx in self.label2id.items()}
            
            # Split data
            train_texts, val_texts, train_labels, val_labels = train_test_split(
                texts, labels, test_size=0.2, random_state=42, stratify=labels
            )
            
            # Create datasets
            train_dataset = TicketDataset(train_texts, train_labels, self.tokenizer, self.max_length)
            val_dataset = TicketDataset(val_texts, val_labels, self.tokenizer, self.max_length)
            
            logger.info(f"Prepared {len(train_texts)} training and {len(val_texts)} validation samples")
            logger.info(f"Labels: {list(self.label2id.keys())}")
            
            return train_dataset, val_dataset
            
        except Exception as e:
            logger.error(f"Failed to prepare data: {e}")
            raise
    
    def fine_tune(self, train_dataset, val_dataset, output_dir: str = None, 
                  epochs: int = 3, batch_size: int = 16, learning_rate: float = 2e-5):
        """Fine-tune BERT model on support ticket data"""
        try:
            # Create output directory
            if not output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(self.models_dir, f"bert_finetuned_{timestamp}")
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Load model with correct number of labels
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                num_labels=len(self.label2id)
            )
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                warmup_steps=500,
                weight_decay=0.01,
                logging_dir=os.path.join(output_dir, "logs"),
                logging_steps=10,
                evaluation_strategy="epoch",
                save_strategy="epoch",
                load_best_model_at_end=True,
                metric_for_best_model="eval_accuracy",
                greater_is_better=True,
            )
            
            # Create trainer
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=val_dataset,
                tokenizer=self.tokenizer,
            )
            
            # Train model
            logger.info("Starting BERT fine-tuning...")
            train_result = trainer.train()
            
            # Save model and tokenizer
            trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)
            
            # Save label mappings
            with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
                json.dump({
                    "label2id": self.label2id,
                    "id2label": self.id2label
                }, f)
            
            # Save training history
            self.training_history.append({
                "timestamp": datetime.now().isoformat(),
                "model_path": output_dir,
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "train_loss": train_result.training_loss,
                "eval_results": trainer.evaluate()
            })
            
            self.model_version = output_dir
            logger.info(f"BERT fine-tuning completed. Model saved to: {output_dir}")
            
            return output_dir
            
        except Exception as e:
            logger.error(f"BERT fine-tuning failed: {e}")
            raise
    
    def predict(self, text: str) -> Tuple[str, float]:
        """
        Predict category for a support ticket
        
        Args:
            text: Input ticket text
            
        Returns:
            Tuple of (category, confidence_score)
        """
        if self.model is None:
            raise ValueError("Model not loaded. Please load a model first.")
        
        try:
            # Tokenize text
            inputs = self.tokenizer(
                text,
                truncation=True,
                padding=True,
                max_length=self.max_length,
                return_tensors="pt"
            )
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=1)
                predicted_class = torch.argmax(probabilities, dim=1).item()
                confidence = probabilities[0][predicted_class].item()
            
            # Get predicted category
            predicted_category = self.id2label[predicted_class]
            
            return predicted_category, confidence
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
    
    def predict_with_confidence_label(self, text: str) -> Dict[str, Any]:
        """
        Predict with detailed confidence information
        
        Args:
            text: Input ticket text
            
        Returns:
            Dictionary with prediction results
        """
        category, confidence = self.predict(text)
        
        # Determine confidence label
        if confidence >= 0.8:
            confidence_label = "high"
        elif confidence >= 0.6:
            confidence_label = "medium"
        else:
            confidence_label = "low"
        
        return {
            "category": category,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "text": text,
            "model_version": self.model_version,
            "classifier_type": "bert"
        }
    
    def batch_predict(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Predict categories for multiple tickets
        
        Args:
            texts: List of ticket texts
            
        Returns:
            List of prediction results
        """
        return [self.predict_with_confidence_label(text) for text in texts]
    
    def evaluate(self, test_data_path: str = "data/sample_tickets.json") -> Dict[str, Any]:
        """Evaluate model performance on test data"""
        try:
            with open(test_data_path, 'r') as f:
                test_data = json.load(f)
            
            y_true = [item['category'] for item in test_data]
            y_pred = []
            confidences = []
            
            for item in test_data:
                category, confidence = self.predict(item['text'])
                y_pred.append(category)
                confidences.append(confidence)
            
            # Calculate metrics
            from app.models.evaluation import model_evaluator
            metrics = model_evaluator.calculate_classification_metrics(y_true, y_pred)
            
            # Add confidence metrics
            metrics.update({
                "average_confidence": np.mean(confidences),
                "model_version": self.model_version,
                "total_predictions": len(y_pred)
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "max_length": self.max_length,
            "num_labels": len(self.label2id),
            "labels": list(self.label2id.keys()),
            "training_history": self.training_history
        }
    
    def load_model(self, model_path: str):
        """Load a specific model version"""
        try:
            self._load_model(model_path)
            self.model_version = model_path
            logger.info(f"Loaded model from: {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

# Global BERT classifier instance
bert_classifier = BERTClassifier() 