from sqlalchemy import create_engine, Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./ghost_budget.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define a User model to store user information.
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    current_balance = Column(Float, default=0.0)
    roth_ira_contribution = Column(Float, default=0.0)
    
    # Relationship with transactions
    transactions = relationship("Transaction", back_populates="owner")

# Define a Transaction model to store expense details.
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    expense_day = Column(Integer)      # e.g., day of the month when the expense occurred
    expense_type = Column(String)        # e.g., "Food", "Bills", etc.
    expense_amount = Column(Float)       # expense amount
    
    # You can add a date field if you need the full date, e.g.,
    # expense_date = Column(Date)
    
    owner = relationship("User", back_populates="transactions")

# Create the tables in the database (for the first time)
Base.metadata.create_all(bind=engine)
