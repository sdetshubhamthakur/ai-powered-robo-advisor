from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np
import pandas as pd
import joblib
from pydantic import BaseModel
from typing import List, Optional, Dict
import uuid
import json
from datetime import datetime
import os

import os

app = FastAPI(title="Robo-Advisor Pre-Screening Tool")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the trained model with error handling
try:
    model = joblib.load("model.joblib")
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"❌ Failed to load model: {e}")
    raise HTTPException(status_code=500, detail="Model loading failed")

# Simplified explainer (no SHAP for production stability)
explainer = None
print("ℹ️ Using simplified explanations (SHAP disabled for production)")

# In-memory storage for demo (use database in production)
assessment_sessions = {}
assessment_logs = []

# Original ClientData model for backward compatibility
class ClientData(BaseModel):
    age: int
    income: int
    risk_tolerance: int
    investment_horizon: int

# New data models for pre-screening tool
class DemographicInfo(BaseModel):
    age: int
    income: int
    employment_status: str  # "employed", "self_employed", "unemployed", "retired"
    location: str
    dependents: int
    marital_status: str  # "single", "married", "divorced", "widowed"
    
    # Add validation
    class Config:
        @staticmethod
        def schema_extra(schema, model_type):
            schema["properties"]["age"]["minimum"] = 18
            schema["properties"]["age"]["maximum"] = 100
            schema["properties"]["income"]["minimum"] = 20000
            schema["properties"]["income"]["maximum"] = 50000000
            schema["properties"]["dependents"]["minimum"] = 0
            schema["properties"]["dependents"]["maximum"] = 20

class FinancialGoals(BaseModel):
    primary_goal: str  # "retirement", "home_purchase", "education", "wealth_building", "emergency_fund"
    target_amount: Optional[int] = None
    time_horizon: int  # years
    current_savings: int
    monthly_expenses: int
    existing_debt: int
    emergency_fund_months: int
    
    # Add validation
    class Config:
        @staticmethod
        def schema_extra(schema, model_type):
            schema["properties"]["target_amount"]["minimum"] = 1000
            schema["properties"]["target_amount"]["maximum"] = 100000000
            schema["properties"]["time_horizon"]["minimum"] = 1
            schema["properties"]["time_horizon"]["maximum"] = 50
            schema["properties"]["current_savings"]["minimum"] = 0
            schema["properties"]["current_savings"]["maximum"] = 50000000
            schema["properties"]["monthly_expenses"]["minimum"] = 0
            schema["properties"]["monthly_expenses"]["maximum"] = 1000000
            schema["properties"]["existing_debt"]["minimum"] = 0
            schema["properties"]["existing_debt"]["maximum"] = 50000000
            schema["properties"]["emergency_fund_months"]["minimum"] = 0
            schema["properties"]["emergency_fund_months"]["maximum"] = 12

class RiskAssessmentResponse(BaseModel):
    question_id: int
    selected_option: str
    score: int

class CompleteAssessment(BaseModel):
    session_id: str
    demographics: DemographicInfo
    financial_goals: FinancialGoals
    risk_responses: List[RiskAssessmentResponse]

# Original endpoints for backward compatibility
@app.post("/predict")
def predict_risk_level(data: ClientData):
    input_df = pd.DataFrame([data.model_dump()])
    prediction = model.predict(input_df)[0]
    
    # Risk level categories
    risk_levels = {
        1: "Very Conservative",
        2: "Conservative", 
        3: "Moderate",
        4: "Aggressive",
        5: "Very Aggressive"
    }
    
    return {
        "predicted_risk_level": int(prediction),
        "risk_category": risk_levels[int(prediction)]
    }

@app.post("/explain")
def explain_risk_level(data: ClientData):
    try:
        input_df = pd.DataFrame([data.model_dump()])
        
        # Get prediction for context
        prediction = model.predict(input_df)[0]
        prediction = int(prediction)  # Ensure it's a scalar
        
        # Use simplified feature importance (Random Forest built-in)
        feature_importance_raw = model.feature_importances_
        feature_names = input_df.columns.tolist()
        feature_importance = dict(zip(feature_names, feature_importance_raw.tolist()))
        
        # Generate user-friendly explanation
        risk_levels = {
            1: "Very Conservative",
            2: "Conservative", 
            3: "Moderate",
            4: "Aggressive",
            5: "Very Aggressive"
        }
        
        # Find the most influential features
        sorted_features = sorted(feature_importance.items(), key=lambda x: abs(x[1]), reverse=True)
        top_positive = [f for f, v in sorted_features if v > 0][:2]
        top_negative = [f for f, v in sorted_features if v < 0][:2]
        
        # Create explanation text
        explanation_text = f"Based on your profile, we recommend a {risk_levels[prediction]} (Level {prediction}) investment strategy. "
        
        if top_positive:
            explanation_text += f"Factors increasing your risk capacity: "
            for feature in top_positive:
                value = input_df[feature].iloc[0]
                if feature == "age":
                    explanation_text += f"your age of {value} years, "
                elif feature == "income":
                    explanation_text += f"your annual income of ${value:,}, "
                elif feature == "risk_tolerance":
                    explanation_text += f"your risk tolerance level of {value}/5, "
                elif feature == "investment_horizon":
                    explanation_text += f"your {value}-year investment timeline, "
            explanation_text = explanation_text.rstrip(", ") + ". "
        
        if top_negative:
            explanation_text += f"Factors suggesting lower risk: "
            for feature in top_negative:
                value = input_df[feature].iloc[0]
                if feature == "age":
                    explanation_text += f"your age of {value} years, "
                elif feature == "income":
                    explanation_text += f"your annual income of ${value:,}, "
                elif feature == "risk_tolerance":
                    explanation_text += f"your risk tolerance level of {value}/5, "
                elif feature == "investment_horizon":
                    explanation_text += f"your {value}-year investment timeline, "
            explanation_text = explanation_text.rstrip(", ") + ". "
        
        return {
            "predicted_risk_level": prediction,
            "risk_category": risk_levels[prediction],
            "user_friendly_explanation": explanation_text,
            "feature_importance": feature_importance,
            "detailed_explanation": {
                name: {
                    "value": float(input_df[name].iloc[0]),
                    "shap_value": float(importance),
                    "impact": "increases" if importance > 0 else "decreases"
                }
                for name, importance in feature_importance.items()
            }
        }
    except Exception as e:
        return {"error": f"Explanation generation failed: {str(e)}"}

# New Pre-Screening Tool API Endpoints

@app.post("/start-assessment")
def start_assessment():
    """Initialize a new assessment session"""
    session_id = str(uuid.uuid4())
    
    assessment_sessions[session_id] = {
        "created_at": datetime.now().isoformat(),
        "status": "started",
        "demographics": None,
        "financial_goals": None,
        "risk_responses": [],
        "completed": False
    }
    
    return {
        "session_id": session_id,
        "message": "Assessment session started",
        "next_step": "/submit-demographics"
    }
@app.post("/submit-demographics")
def submit_demographics(session_id: str, demographics: DemographicInfo):
    """Submit demographic information"""
    if session_id not in assessment_sessions:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    # Additional validation
    if not (18 <= demographics.age <= 100):
        raise HTTPException(status_code=400, detail="Age must be between 18 and 100")
    if not (20000 <= demographics.income <= 50000000):
        raise HTTPException(status_code=400, detail="Income must be between $20,000 and $50 million")
    if not (0 <= demographics.dependents <= 20):
        raise HTTPException(status_code=400, detail="Number of dependents must be between 0 and 20")
    
    assessment_sessions[session_id]["demographics"] = demographics.dict()
    assessment_sessions[session_id]["status"] = "demographics_complete"
    
    return {
        "session_id": session_id,
        "message": "Demographics saved successfully",
        "next_step": "/submit-financial-goals"
    }

@app.post("/submit-financial-goals")
def submit_financial_goals(session_id: str, financial_goals: FinancialGoals):
    """Submit financial goals and situation"""
    if session_id not in assessment_sessions:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    # Additional validation
    if financial_goals.target_amount is not None and not (1000 <= financial_goals.target_amount <= 100000000):
        raise HTTPException(status_code=400, detail="Target amount must be between $1,000 and $100 million")
    if not (1 <= financial_goals.time_horizon <= 50):
        raise HTTPException(status_code=400, detail="Time horizon must be between 1 and 50 years")
    if not (0 <= financial_goals.current_savings <= 50000000):
        raise HTTPException(status_code=400, detail="Current savings must be between $0 and $50 million")
    if not (0 <= financial_goals.monthly_expenses <= 1000000):
        raise HTTPException(status_code=400, detail="Monthly expenses must be between $0 and $1 million")
    if not (0 <= financial_goals.existing_debt <= 50000000):
        raise HTTPException(status_code=400, detail="Existing debt must be between $0 and $50 million")
    if not (0 <= financial_goals.emergency_fund_months <= 12):
        raise HTTPException(status_code=400, detail="Emergency fund must be between 0 and 12 months")
    
    assessment_sessions[session_id]["financial_goals"] = financial_goals.dict()
    assessment_sessions[session_id]["status"] = "financial_goals_complete"
    
    return {
        "session_id": session_id,
        "message": "Financial goals saved successfully",
        "next_step": "/get-risk-questions"
    }

@app.get("/get-risk-questions")
def get_risk_questions():
    """Get risk tolerance assessment questions"""
    questions = [
        {
            "id": 1,
            "category": "experience",
            "question": "How would you describe your investment experience?",
            "type": "single_choice",
            "options": [
                {"value": "none", "text": "No prior investment experience", "score": 1},
                {"value": "beginner", "text": "Less than 2 years", "score": 2},
                {"value": "intermediate", "text": "2-10 years of experience", "score": 3},
                {"value": "expert", "text": "More than 10 years of experience", "score": 4}
            ]
        },
        {
            "id": 2,
            "category": "loss_tolerance",
            "question": "If your investments lost 20% of their value in one year, what would you do?",
            "type": "single_choice",
            "options": [
                {"value": "sell_all", "text": "Sell everything to avoid further losses", "score": 1},
                {"value": "sell_some", "text": "Sell some investments to limit losses", "score": 2},
                {"value": "hold", "text": "Hold everything and wait for recovery", "score": 3},
                {"value": "buy_more", "text": "Buy more at the lower prices", "score": 4}
            ]
        },
        {
            "id": 3,
            "category": "volatility_comfort",
            "question": "What's the maximum loss you could accept in a single year?",
            "type": "single_choice",
            "options": [
                {"value": "5_percent", "text": "5% - I need stability", "score": 1},
                {"value": "10_percent", "text": "10% - Small fluctuations are OK", "score": 2},
                {"value": "20_percent", "text": "20% - I can handle moderate swings", "score": 3},
                {"value": "30_plus", "text": "30%+ - I'm comfortable with high volatility", "score": 4}
            ]
        },
        {
            "id": 4,
            "category": "time_pressure",
            "question": "When do you expect to need this money?",
            "type": "single_choice",
            "options": [
                {"value": "less_2_years", "text": "Less than 2 years", "score": 1},
                {"value": "2_5_years", "text": "2-5 years", "score": 2},
                {"value": "5_10_years", "text": "5-10 years", "score": 3},
                {"value": "more_10_years", "text": "More than 10 years", "score": 4}
            ]
        },
        {
            "id": 5,
            "category": "priority",
            "question": "What's most important to you?",
            "type": "single_choice",
            "options": [
                {"value": "preserve_capital", "text": "Preserving my money (avoiding losses)", "score": 1},
                {"value": "steady_income", "text": "Generating steady income", "score": 2},
                {"value": "balanced_growth", "text": "Balanced growth with some income", "score": 3},
                {"value": "maximize_growth", "text": "Maximizing long-term growth", "score": 4}
            ]
        }
    ]
    
    return {
        "total_questions": len(questions),
        "questions": questions
    }

@app.post("/submit-risk-assessment")
def submit_risk_assessment(session_id: str, risk_responses: List[RiskAssessmentResponse]):
    """Submit risk tolerance responses"""
    if session_id not in assessment_sessions:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    assessment_sessions[session_id]["risk_responses"] = [r.dict() for r in risk_responses]
    assessment_sessions[session_id]["status"] = "risk_assessment_complete"
    
    return {
        "session_id": session_id,
        "message": "Risk assessment completed successfully",
        "next_step": "/generate-recommendation"
    }

@app.post("/generate-recommendation")
def generate_recommendation(session_id: str):
    """Generate comprehensive investment recommendation"""
    if session_id not in assessment_sessions:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    session = assessment_sessions[session_id]
    
    # Validate all data is present
    if not all([session["demographics"], session["financial_goals"], session["risk_responses"]]):
        raise HTTPException(status_code=400, detail="Incomplete assessment data")
    
    # Calculate risk tolerance from questionnaire
    total_score = sum([r["score"] for r in session["risk_responses"]])
    max_possible_score = len(session["risk_responses"]) * 4
    normalized_score = (total_score / max_possible_score) * 4 + 1
    calculated_risk_tolerance = max(1, min(5, round(normalized_score)))
    
    # Prepare data for ML model
    ml_input = {
        "age": session["demographics"]["age"],
        "income": session["demographics"]["income"],
        "risk_tolerance": calculated_risk_tolerance,
        "investment_horizon": session["financial_goals"]["time_horizon"]
    }
    
    # Get ML prediction
    input_df = pd.DataFrame([ml_input])
    ml_prediction = model.predict(input_df)[0]
    
    # Use simplified feature importance
    feature_importance_raw = model.feature_importances_
    feature_names = input_df.columns.tolist()
    feature_importance = dict(zip(feature_names, feature_importance_raw.tolist()))
    
    # Generate portfolio allocation
    portfolio_allocation = generate_portfolio_allocation(int(ml_prediction), session)
    
    # Calculate projections
    projections = calculate_projections(session, portfolio_allocation)
    
    # Create comprehensive recommendation
    recommendation = {
        "session_id": session_id,
        "assessment_summary": {
            "questionnaire_risk_score": calculated_risk_tolerance,
            "ml_predicted_risk_score": int(ml_prediction),
            "final_risk_category": get_risk_category(int(ml_prediction))
        },
        "portfolio_recommendation": portfolio_allocation,
        "projections": projections,
        "explanation": generate_explanation(session, feature_importance, int(ml_prediction)),
        "next_steps": generate_next_steps(session),
        "disclaimer": "This recommendation is for educational purposes only and should not be considered as financial advice."
    }
    
    # Mark session as completed and log the data
    session["completed"] = True
    session["recommendation"] = recommendation
    session["completed_at"] = datetime.now().isoformat()
    
    # Log the assessment data
    log_assessment_data(session)
    
    return recommendation

def generate_portfolio_allocation(risk_level: int, session: dict):
    """Generate portfolio allocation based on risk level and user profile"""
    base_allocations = {
        1: {"stocks": 20, "bonds": 70, "cash": 10},
        2: {"stocks": 40, "bonds": 50, "cash": 10},
        3: {"stocks": 60, "bonds": 35, "cash": 5},
        4: {"stocks": 80, "bonds": 20, "cash": 0},
        5: {"stocks": 90, "bonds": 10, "cash": 0}
    }
    
    allocation = base_allocations[risk_level].copy()
    
    # Adjust based on user profile
    demographics = session["demographics"]
    financial_goals = session["financial_goals"]
    
    # Age adjustment
    if demographics["age"] > 60:
        allocation["bonds"] += 10
        allocation["stocks"] -= 10
    
    # Emergency fund adjustment
    if financial_goals["emergency_fund_months"] < 3:
        allocation["cash"] += 10
        allocation["stocks"] -= 10
    
    # Ensure allocations sum to 100
    total = sum(allocation.values())
    if total != 100:
        diff = 100 - total
        allocation["stocks"] += diff
    
    return {
        "allocation": allocation,
        "recommended_monthly_investment": calculate_recommended_investment(session),
        "rebalancing_frequency": "quarterly"
    }

def calculate_projections(session: dict, portfolio_allocation: dict):
    """Calculate investment projections"""
    expected_returns = {"stocks": 0.08, "bonds": 0.04, "cash": 0.02}
    
    allocation = portfolio_allocation["allocation"]
    portfolio_return = sum([
        allocation[asset] / 100 * expected_returns[asset] 
        for asset in allocation
    ])
    
    financial_goals = session["financial_goals"]
    current_value = financial_goals["current_savings"]
    monthly_contribution = portfolio_allocation["recommended_monthly_investment"]
    years = financial_goals["time_horizon"]
    
    # Calculate future value
    future_value = calculate_future_value(current_value, monthly_contribution, portfolio_return, years)
    
    return {
        "expected_annual_return": f"{portfolio_return:.1%}",
        "projected_portfolio_value": f"${future_value:,.0f}",
        "monthly_contribution_needed": f"${monthly_contribution:,.0f}",
        "goal_achievement": {
            "target_amount": financial_goals.get("target_amount", 0),
            "projected_amount": future_value,
            "likely_to_achieve": future_value >= financial_goals.get("target_amount", 0) if financial_goals.get("target_amount") else True
        }
    }

def calculate_recommended_investment(session: dict):
    """Calculate recommended monthly investment amount"""
    demographics = session["demographics"]
    financial_goals = session["financial_goals"]
    
    monthly_income = demographics["income"] / 12
    monthly_surplus = monthly_income - financial_goals["monthly_expenses"]
    
    # Recommend 20% of surplus, minimum $100, maximum $2000
    recommended = max(100, min(2000, monthly_surplus * 0.2))
    
    return round(recommended, 0)

def calculate_future_value(present_value, monthly_payment, annual_rate, years):
    """Calculate future value with compound interest"""
    monthly_rate = annual_rate / 12
    months = years * 12
    
    # Future value of present amount
    fv_present = present_value * (1 + annual_rate) ** years
    
    # Future value of monthly payments (annuity)
    if monthly_rate > 0:
        fv_payments = monthly_payment * (((1 + monthly_rate) ** months - 1) / monthly_rate)
    else:
        fv_payments = monthly_payment * months
    
    return fv_present + fv_payments

def generate_explanation(session: dict, feature_importance: dict, risk_level: int):
    """Generate user-friendly explanation"""
    risk_categories = {
        1: "Very Conservative", 2: "Conservative", 3: "Moderate",
        4: "Aggressive", 5: "Very Aggressive"
    }
    
    demographics = session["demographics"]
    
    explanation = f"Based on your comprehensive assessment, we recommend a {risk_categories[risk_level]} (Level {risk_level}) investment strategy. "
    
    # Add specific reasoning based on user profile
    if demographics["age"] < 30:
        explanation += "Your young age gives you a long time horizon to recover from market volatility. "
    elif demographics["age"] > 55:
        explanation += "Given your age, we've adjusted your portfolio to be more conservative to protect your wealth. "
    
    if risk_level <= 2:
        explanation += "This conservative approach focuses on capital preservation with steady, predictable returns. "
    elif risk_level >= 4:
        explanation += "This aggressive strategy maximizes growth potential while accepting higher volatility. "
    else:
        explanation += "This balanced approach provides growth potential while managing risk. "
    
    return explanation

def generate_next_steps(session: dict):
    """Generate actionable next steps"""
    steps = [
        "Review and understand your recommended portfolio allocation",
        "Consider opening investment accounts if you don't have them",
        "Set up automatic monthly investments to stay consistent",
        "Review and rebalance your portfolio quarterly"
    ]
    
    financial_goals = session["financial_goals"]
    if financial_goals["emergency_fund_months"] < 6:
        steps.insert(1, "Build an emergency fund of 3-6 months of expenses before investing")
    
    if financial_goals["existing_debt"] > financial_goals["current_savings"]:
        steps.insert(1, "Consider paying down high-interest debt before investing")
    
    return steps

def get_risk_category(risk_level: int):
    """Get risk category description"""
    categories = {
        1: "Very Conservative", 2: "Conservative", 3: "Moderate",
        4: "Aggressive", 5: "Very Aggressive"
    }
    return categories.get(risk_level, "Moderate")

def log_assessment_data(session: dict):
    """Log assessment data for analytics"""
    log_entry = {
        "session_id": session.get("session_id"),
        "timestamp": datetime.now().isoformat(),
        "demographics": session.get("demographics"),
        "financial_goals": session.get("financial_goals"),
        "risk_responses": session.get("risk_responses"),
        "recommendation": session.get("recommendation", {}).get("assessment_summary"),
        "completed": session.get("completed", False)
    }
    
    assessment_logs.append(log_entry)
    
    # Also save to file for persistence
    log_file = "assessment_logs.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

@app.get("/get-assessment-logs")
def get_assessment_logs():
    """Get all assessment logs (admin endpoint)"""
    return {
        "total_assessments": len(assessment_logs),
        "logs": assessment_logs
    }

@app.get("/session-status/{session_id}")
def get_session_status(session_id: str):
    """Get current session status"""
    if session_id not in assessment_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = assessment_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session["status"],
        "completed": session.get("completed", False),
        "created_at": session["created_at"]
    }

# Root endpoint
@app.get("/")
def root():
    return {
        "message": "Robo-Advisor Pre-Screening Tool API",
        "available_endpoints": [
            "/start-assessment",
            "/submit-demographics", 
            "/submit-financial-goals",
            "/get-risk-questions",
            "/submit-risk-assessment",
            "/generate-recommendation"
        ],
        "legacy_endpoints": ["/predict", "/explain"],
        "docs": "/docs"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
