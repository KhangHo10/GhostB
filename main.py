import os

# -------------------------------
# Delete the Database File (for development)
# -------------------------------
DATABASE_FILE = "./ghost_budget.db"
if os.path.exists(DATABASE_FILE):
    try:
        os.remove(DATABASE_FILE)
        print("Old database file removed.")
    except PermissionError as e:
        print("Could not remove database file:", e)

DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# -------------------------------
# Imports
# -------------------------------
from fastapi import FastAPI, HTTPException, Depends, Body
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
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    current_balance = Column(Float, default=10000.0)  # Default balance: $10,000
    roth_ira_contribution = Column(Float, default=0.0)
    high_yield_savings = Column(Float, default=0.0)
    ghost_budget = Column(Float, default=0.0)
    
    transactions = relationship("Transaction", back_populates="owner")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    expense_date = Column(Date)  # e.g., "2025-02-21"
    expense_type = Column(String)    # e.g., "Food", "Bills", etc.
    expense_amount = Column(Float)   # Expense amount
    
    owner = relationship("User", back_populates="transactions")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# Helper Function for Charge Calculation
# -------------------------------
def calculate_adjusted_charge(actual_charge: float, unnecessary_spending: float) -> float:
    threshold = 100.0
    factor = 0.012  # Reduced factor: 1.2% per dollar above threshold
    if unnecessary_spending > threshold:
        excess = unnecessary_spending - threshold
        multiplier = 1 + (excess * factor)
    else:
        multiplier = 1.0
    return actual_charge * multiplier

# -------------------------------
# Machine Learning Model Setup
# -------------------------------
expense_type_mapping = {
    "Food": 0,
    "Entertainment": 1,
    "Shopping": 2,
    "Bills": 3,
    "Transport": 4
}

try:
    with open("spending_model.pkl", "rb") as file:
        model = pickle.load(file)
except Exception as e:
    raise RuntimeError("Model file not found or failed to load") from e

# -------------------------------
# Pydantic Schemas
# -------------------------------
class TransactionData(BaseModel):
    expense_date: date
    expense_type: str
    amount: float

class UserCreate(BaseModel):
    username: str

class UserUpdate(BaseModel):
    user_id: int
    current_balance: float
    roth_ira_contribution: float
    high_yield_savings: float
    ghost_budget: float

class TransactionCreate(BaseModel):
    user_id: int
    expense_date: date
    expense_type: str
    expense_amount: float

class ChargeCalculationInput(BaseModel):
    actual_charge: float
    unnecessary_spending: float

class ChargeCalculationOutput(BaseModel):
    adjusted_charge: float

# For expense processing from the search container (no user_id required for demo)
class ExpenseCalcInput(BaseModel):
    expense_date: date
    expense_type: str
    amount: float

# -------------------------------
# FastAPI App and Endpoints
# -------------------------------
app = FastAPI(title="Ghost Budget Prediction and Data API")

# Add CORS Middleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. ML Prediction Endpoint
@app.post("/predict", summary="Predict if an expense is necessary or unnecessary")
def predict_spending(data: TransactionData):
    try:
        day = data.expense_date.day
        amount_log = np.log1p(data.amount)
        day_sin = np.sin(day * (2 * np.pi / 30))
        day_cos = np.cos(day * (2 * np.pi / 30))
        if data.expense_type in expense_type_mapping:
            category = expense_type_mapping[data.expense_type]
        else:
            raise HTTPException(status_code=400, detail="Unknown expense type")
        median_amount = 100.0
        high_amount = 1 if data.amount > median_amount else 0
        amount_day_interaction = amount_log * day_sin
        features = np.array([
            amount_log,
            day_sin,
            day_cos,
            high_amount,
            amount_day_interaction
        ]).reshape(1, -1)
        prediction = model.predict(features)
        probability = model.predict_proba(features)[0, 1] if hasattr(model, "predict_proba") else None
        return {
            "prediction": int(prediction[0]),
            "probability": probability
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. Endpoint to Create a New User
@app.post("/users/", summary="Create a new user")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    db_user = User(
        username=user.username,
        current_balance=10000.0,
        roth_ira_contribution=0.0,
        high_yield_savings=0.0,
        ghost_budget=0.0
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 3. Endpoint to Record a New Transaction
@app.post("/transactions/", summary="Record a new transaction")
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db_transaction = Transaction(
        user_id=transaction.user_id,
        expense_date=transaction.expense_date,
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

# 5. Endpoint to Calculate Adjusted Charge
@app.post("/calculate-charge", response_model=ChargeCalculationOutput, summary="Calculate adjusted charge based on unnecessary spending")
def calculate_charge(data: ChargeCalculationInput):
    try:
        adjusted = calculate_adjusted_charge(data.actual_charge, data.unnecessary_spending)
        return {"adjusted_charge": adjusted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 6. Endpoint to Process Expense Input and Update ghost_budget
@app.post("/transactions/calc", summary="Process expense input and determine final charge")
def process_expense(expense: ExpenseCalcInput, db: Session = Depends(get_db)):
    try:
        day = expense.expense_date.day
        amount_log = np.log1p(expense.amount)
        day_sin = np.sin(day * (2 * np.pi / 30))
        day_cos = np.cos(day * (2 * np.pi / 30))
        if expense.expense_type in expense_type_mapping:
            category = expense_type_mapping[expense.expense_type]
        else:
            raise HTTPException(status_code=400, detail="Unknown expense type")
        median_amount = 100.0
        high_amount = 1 if expense.amount > median_amount else 0
        amount_day_interaction = amount_log * day_sin
        
        import pandas as pd
        features = pd.DataFrame({
            "amount_log": [amount_log],
            "day_sin": [day_sin],
            "day_cos": [day_cos],
            "high_amount": [high_amount],
            "amount_day_interaction": [amount_day_interaction]
        })
        
        prediction = int(model.predict(features)[0])
        if prediction == 1:
            final_charge = calculate_adjusted_charge(expense.amount, unnecessary_spending=150)
            charge_type = "fake"
        else:
            final_charge = expense.amount
            charge_type = "real"
        
        difference = final_charge - expense.amount if charge_type == "fake" else 0
        
        # Use default demo user with id = 1; auto-create if not exists
        default_user_id = 1
        user = db.query(User).filter(User.id == default_user_id).first()
        if not user:
            user = User(
                username="demo",
                current_balance=10000.0,
                roth_ira_contribution=0.0,
                high_yield_savings=0.0,
                ghost_budget=0.0
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Deduct the final charge from current_balance and update ghost_budget
        user.current_balance -= final_charge
        user.ghost_budget += difference
        db.commit()
        db.refresh(user)
        
        return {
            "expense_date": expense.expense_date.isoformat(),
            "expense_type": expense.expense_type,
            "original_amount": expense.amount,
            "final_charge": final_charge,
            "charge_type": charge_type,
            "prediction": prediction,
            "difference": difference,
            "new_ghost_budget": user.ghost_budget,
            "new_current_balance": user.current_balance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 7. Endpoint for "Claim" Action: Transfer ghost_budget back to bank account
class UserID(BaseModel):
    user_id: int

@app.post("/users/claim", summary="Claim ghost budget to bank account")
def claim_ghost_budget(user: UserID, db: Session = Depends(get_db)):
    user_obj = db.query(User).filter(User.id == user.user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    user_obj.current_balance += user_obj.ghost_budget
    user_obj.ghost_budget = 0.0
    db.commit()
    db.refresh(user_obj)
    return {
        "message": "Ghost budget claimed and transferred to bank account.",
        "current_balance": user_obj.current_balance,
        "new_ghost_budget": user_obj.ghost_budget
    }

# 8. Endpoint for "Continue Saving" Action: Distribute ghost_budget
@app.post("/users/continue-saving", summary="Distribute ghost budget to Roth IRA and High Yield Savings")
def continue_saving(user: UserID, db: Session = Depends(get_db)):
    user_obj = db.query(User).filter(User.id == user.user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    half = user_obj.ghost_budget / 2
    user_obj.roth_ira_contribution += half
    user_obj.high_yield_savings += half
    user_obj.ghost_budget = 0.0
    db.commit()
    db.refresh(user_obj)
    return {
        "message": "Ghost budget distributed equally between Roth IRA and High Yield Savings.",
        "roth_ira_contribution": user_obj.roth_ira_contribution,
        "high_yield_savings": user_obj.high_yield_savings,
        "new_ghost_budget": user_obj.ghost_budget
    }

# -------------------------------
# Run the Application
# -------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
