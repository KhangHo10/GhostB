# GhostB 💰

GhostB is a full-stack financial management web application that **leverages machine learning** to analyze spending behavior and encourage mindful budgeting. Unlike traditional budgeting apps, GhostB introduces a **cognitive spending mechanism** that inflates unnecessary expense charges to make users more aware of their spending habits, helping them save more effectively.

## Features 🚀

- **Real-Time Expense Classification** 
- **Cognitive Spending Mechanism**
- **Ghost Budget System**
- **Automated Savings Allocation**
- **Full-Stack Implementation** 

## Tech Stack 🏗️  

- **Frontend: HTML, CSS, JavaScript**
- **Backend: FastAPI, SQLAlchemy, SQLite, Scikit-learn, Pydantic, Uvicorn** 

## Visual 📸

[![Watch the demo](https://img.youtube.com/vi/dicX5VP31wc/0.jpg)](https://www.youtube.com/watch?v=dicX5VP31wc)  

## Installation 🔧

1. Create a codespace within GitHub
2. Type "pip install -r requirements.txt"
3. Then type "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
4. Then type localhost:3000 on your browser

## How It Works 📖 

1. **Users enter an expense** (date, type, and amount).  
2. **The ML model analyzes the expense** and determines if it is **necessary or unnecessary**.  
3. **If unnecessary**, the system inflates the charge **by up to 60%**, making the user more mindful of extra spending.  
4. **The extra "ghost budget" is saved**, and users can **claim it back** or allocate it to savings.

   

