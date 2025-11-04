#!/usr/bin/env python3
"""
Simplified training script for production deployment
No MLflow dependency, direct model saving
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import os

def create_synthetic_data(n_samples=1000):
    """Create synthetic financial data for training"""
    np.random.seed(42)
    
    # Generate features
    age = np.random.randint(18, 80, n_samples)
    income = np.random.lognormal(10.5, 0.8, n_samples) * 1000
    income = np.clip(income, 20000, 500000)  # Realistic income range
    
    risk_tolerance = np.random.randint(1, 6, n_samples)
    investment_horizon = np.random.randint(1, 41, n_samples)
    
    # Create risk level based on logical rules
    risk_level = []
    for i in range(n_samples):
        base_risk = risk_tolerance[i]
        
        # Age factor (younger = higher risk)
        if age[i] < 30:
            age_factor = 1
        elif age[i] < 50:
            age_factor = 0
        else:
            age_factor = -1
            
        # Income factor (higher income = higher risk capacity)
        if income[i] > 100000:
            income_factor = 1
        elif income[i] > 60000:
            income_factor = 0
        else:
            income_factor = -1
            
        # Time horizon factor (longer = higher risk)
        if investment_horizon[i] > 20:
            time_factor = 1
        elif investment_horizon[i] > 10:
            time_factor = 0
        else:
            time_factor = -1
            
        # Calculate final risk level
        final_risk = base_risk + age_factor + income_factor + time_factor
        final_risk = max(1, min(5, final_risk))  # Clamp between 1-5
        risk_level.append(final_risk)
    
    # Create DataFrame
    data = pd.DataFrame({
        'age': age,
        'income': income,
        'risk_tolerance': risk_tolerance,
        'investment_horizon': investment_horizon,
        'risk_level': risk_level
    })
    
    return data

def train_model():
    """Train the risk assessment model"""
    print("🔄 Generating synthetic training data...")
    
    # Create or load data
    if os.path.exists('synthetic_robo_advisor_data.csv'):
        print("📁 Loading existing dataset...")
        df = pd.read_csv('synthetic_robo_advisor_data.csv')
    else:
        print("🎲 Creating synthetic dataset...")
        df = create_synthetic_data(5000)
        df.to_csv('synthetic_robo_advisor_data.csv', index=False)
    
    # Prepare features and target
    feature_columns = ['age', 'income', 'risk_tolerance', 'investment_horizon']
    X = df[feature_columns]
    y = df['risk_level']
    
    print(f"📊 Training data shape: {X.shape}")
    print(f"📊 Target distribution: {y.value_counts().sort_index().to_dict()}")
    
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Train Random Forest model
    print("🤖 Training Random Forest model...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate model
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    
    print(f"✅ Model trained successfully!")
    print(f"📈 Training accuracy: {train_score:.3f}")
    print(f"📈 Test accuracy: {test_score:.3f}")
    
    # Save the model
    joblib.dump(model, 'model.joblib')
    print("💾 Model saved as model.joblib")
    
    return model

if __name__ == "__main__":
    try:
        model = train_model()
        print("🎉 Training completed successfully!")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        raise
