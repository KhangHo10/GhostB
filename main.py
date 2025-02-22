# main.py

import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from datetime import date
import pickle
import numpy as np
import uvicorn

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

# -------------------------------
# Database Setup
# -------------------------------

DATABASE_FILE = "./ghost_budget.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Delete the database file if it exists to ensure a fresh start
if os.path.exists(DATABASE_FILE):
    os.remove(DATABASE_FILE)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User model stores user financial data
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    current_balance = Column(Float, default=0.0)
    roth_ira_contribution = Column(Float, default=0.0)
    high_yield_savings = Column(Float, default=0.0)
    ghost_budget = Column(Float, default=0.0)
    
    transactions = relationship("Transaction", back_populates="owner")

# Transaction model stores expense information
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    expense_date = Column(Date)  # Day of the month when the expense occurred
    expense_type = Column(String)    # e.g., "Food", "Bills", etc.
    expense_amount = Column(Float)   # Expense amount
    
    owner = relationship("User", back_populates="transactions")

# Create the database tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# Machine Learning Model Setup
# -------------------------------

# Mapping for expense types (adjust as needed)
expense_type_mapping = {
    "Food": 0,
    "Entertainment": 1,
    "Shopping": 2,
    "Bills": 3,
    "Transport": 4
}

# Load your pre-trained model from a pickle file
try:
    with open("spending_model.pkl", "rb") as file:
        model = pickle.load(file)
except Exception as e:
    raise RuntimeError("Model file not found or failed to load") from e

# -------------------------------
# Pydantic Schemas
# -------------------------------

# For ML prediction
class TransactionData(BaseModel):
    expense_date: date  # e.g., "2025-02-21", parsed into a date object
    expense_type: str
    amount: float

# For creating a new user (only username required)
class UserCreate(BaseModel):
    username: str

# For updating user's financial data
class UserUpdate(BaseModel):
    user_id: int
    current_balance: float
    roth_ira_contribution: float
    high_yield_savings: float
    ghost_budget: float

# For creating a new transaction in the database
class TransactionCreate(BaseModel):
    user_id: int
    expense_date: date   
    expense_type: str
    expense_amount: float

# -------------------------------
# FastAPI App and Endpoints
# -------------------------------

app = FastAPI(title="Ghost Budget Prediction and Data API")

# 1. ML Prediction Endpoint
@app.post("/predict", summary="Predict if an expense is necessary or unnecessary")
def predict_spending(data: TransactionData):
    try:
        # Extract the day from expense_date
        day = data.expense_date.day

        # Compute log-transformed amount
        amount_log = np.log1p(data.amount)

        # Compute cyclic features for the day (assuming 30 days in a month)
        day_sin = np.sin(day * (2 * np.pi / 30))
        day_cos = np.cos(day * (2 * np.pi / 30))
        
        # Map expense_type to a numeric category
        if data.expense_type in expense_type_mapping:
            category = expense_type_mapping[data.expense_type]
        else:
            raise HTTPException(status_code=400, detail="Unknown expense type")
        
        # Define high_amount based on a threshold (adjust median_amount as needed)
        median_amount = 100.0  # Replace with your actual median value
        high_amount = 1 if data.amount > median_amount else 0
        
        # Create an interaction feature
        amount_day_interaction = amount_log * day_sin
        
        # Construct the feature vector with exactly 5 features (order must match your training)
        features = np.array([
            amount_log,
            day_sin,
            day_cos,
            high_amount,
            amount_day_interaction
        ]).reshape(1, -1)
        
        # Make the prediction
        prediction = model.predict(features)
        probability = model.predict_proba(features)[0, 1] if hasattr(model, "predict_proba") else None
        
        return {
            "prediction": int(prediction[0]),
            "probability": probability
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. Endpoint to Create a New User (only username needed)
@app.post("/users/", summary="Create a new user")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    db_user = User(
        username=user.username,
        current_balance=0.0,
        roth_ira_contribution=0.0,
        high_yield_savings=0.0
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/transactions/", summary="Record a new transaction")
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    # Optionally, verify that the user exists
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_transaction = Transaction(
        user_id=transaction.user_id,
        expense_date=transaction.expense_date,  # Use expense_date from the Pydantic model
        expense_type=transaction.expense_type,
        expense_amount=transaction.expense_amount
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


# 4. Endpoint to Update a User's Financial Data
@app.put("/users/update-financials/", summary="Update user's financial data")
def update_user_financials(update: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == update.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.current_balance = update.current_balance
    user.roth_ira_contribution = update.roth_ira_contribution
    user.high_yield_savings = update.high_yield_savings
    user.ghost_budget = update.ghost_budget
    
    db.commit()
    db.refresh(user)
    return user

# -------------------------------
# Run the Application
# -------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
