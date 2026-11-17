from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
import hashlib

DATABASE_URL = "sqlite:///./fincore_fresh.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, unique=True, index=True)
    user_email = Column(String, index=True)
    currency = Column(String, default="INR")
    account_type = Column(String, default="SAVINGS")
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String, unique=True, index=True)
    from_account = Column(String)
    to_account = Column(String)
    amount = Column(Float)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String)
    principal_amount = Column(Float)
    tenure_months = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String)
    principal_amount = Column(Float)
    tenure_months = Column(Integer)
    monthly_emi = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="FinCore Autonomous Engine", version="7.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class TransferCreate(BaseModel):
    from_account_number: str
    to_account_number: str
    amount: float
    description: str = None

class VaultCreate(BaseModel):
    currency: str
    account_type: str
    initial_deposit: float = 0.0

class FDCreate(BaseModel):
    account_number: str
    principal_amount: float
    tenure_months: int

class LoanCreate(BaseModel):
    account_number: str
    principal_amount: float
    tenure_months: int

@app.post("/api/v1/auth/register")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    hashed_pw = hashlib.sha256(user_in.password.encode()).hexdigest()
    user = User(full_name=user_in.full_name, email=user_in.email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)

    if db.query(Account).filter(Account.user_email == user.email).count() == 0:
        default_acc = Account(
            account_number=f"ACC-{user.id}-INR",
            user_email=user.email,
            currency="INR",
            account_type="SAVINGS",
            balance=100000.0
        )
        db.add(default_acc)
        db.commit()
    return {"id": user.id, "full_name": user.full_name, "email": user.email}

@app.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": f"token-for-{user.email}", "token_type": "bearer"}

@app.get("/api/v1/accounts/")
def get_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()

@app.post("/api/v1/accounts/")
def create_account(vault: VaultCreate, db: Session = Depends(get_db)):
    new_acc = Account(
        account_number=f"ACC-{int(datetime.utcnow().timestamp())}-{vault.currency}",
        user_email="satyasaibareddy16@gmail.com",
        currency=vault.currency,
        account_type=vault.account_type,
        balance=vault.initial_deposit
    )
    db.add(new_acc)
    db.commit()
    return {"status": "Vault Created", "account_number": new_acc.account_number}

@app.delete("/api/v1/accounts/{account_number:path}")
def delete_account(account_number: str, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.account_number == account_number).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Account {account_number} not found.")
    if acc.balance > 0:
        raise HTTPException(status_code=400, detail="Cannot delete account with remaining balance. Transfer funds first.")
    db.delete(acc)
    db.commit()
    return {"status": "Account Deleted Successfully"}

@app.get("/api/v1/transactions/")
def get_transactions(db: Session = Depends(get_db)):
    return db.query(Transaction).order_by(Transaction.created_at.desc()).all()

@app.post("/api/v1/transactions/transfer")
def transfer(tx: TransferCreate, db: Session = Depends(get_db)):
    sender = db.query(Account).filter(Account.account_number == tx.from_account_number).first()
    receiver = db.query(Account).filter(Account.account_number == tx.to_account_number).first()

    if not sender:
        raise HTTPException(status_code=400, detail="Source account number does not exist.")
    if not receiver:
        raise HTTPException(status_code=400, detail="Destination account number does not exist.")
    if sender.balance < tx.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds in source account.")

    sender.balance -= tx.amount
    receiver.balance += tx.amount

    new_tx = Transaction(
        reference_id=f"TXN-{int(datetime.utcnow().timestamp())}",
        from_account=tx.from_account_number,
        to_account=tx.to_account_number,
        amount=tx.amount,
        description=tx.description or "Direct Account-to-Account Settlement"
    )
    db.add(new_tx)
    db.commit()
    return {"status": "Success", "reference_id": new_tx.reference_id}

@app.get("/api/v1/fixed-deposits/")
def get_fds(db: Session = Depends(get_db)):
    return db.query(FixedDeposit).all()

@app.post("/api/v1/fixed-deposits/")
def create_fd(fd: FDCreate, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.account_number == fd.account_number).first()
    if not acc:
        raise HTTPException(status_code=400, detail="Invalid account number.")
    if fd.principal_amount < 5000:
        raise HTTPException(status_code=400, detail="Minimum Fixed Deposit principal is ₹5,000.")
    if fd.principal_amount > acc.balance:
        raise HTTPException(status_code=400, detail="FD principal cannot exceed available account balance.")

    acc.balance -= fd.principal_amount
    new_fd = FixedDeposit(
        account_number=fd.account_number,
        principal_amount=fd.principal_amount,
        tenure_months=fd.tenure_months
    )
    db.add(new_fd)
    db.commit()
    return {"status": "FD Locked Successfully"}

@app.get("/api/v1/loans/")
def get_loans(db: Session = Depends(get_db)):
    return db.query(Loan).all()

@app.post("/api/v1/loans/apply")
def apply_loan(loan: LoanCreate, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.account_number == loan.account_number).first()
    if not acc:
        raise HTTPException(status_code=400, detail="Invalid account number.")
    if loan.principal_amount < 10000 or loan.principal_amount > 2500000:
        raise HTTPException(status_code=400, detail="Loan amount must be between ₹10,000 and ₹25,00,000.")

    monthly_emi = (loan.principal_amount * 1.10) / loan.tenure_months
    acc.balance += loan.principal_amount

    new_loan = Loan(
        account_number=loan.account_number,
        principal_amount=loan.principal_amount,
        tenure_months=loan.tenure_months,
        monthly_emi=monthly_emi
    )
    db.add(new_loan)
    db.commit()
    return {"status": "Loan Disbursed Successfully", "emi": monthly_emi}

@app.get("/api/v1/risk/alerts")
def get_alerts(): return []

@app.post("/api/v1/copilot/chat")
def copilot_chat(payload: dict, db: Session = Depends(get_db)):
    msg = payload.get("message", "").lower()
    accounts = db.query(Account).all()
    total_bal = sum(a.balance for a in accounts)
    return {"reply": f"FinCore Neural Ledger parsed your query ('{msg}'). Total active liquidity across {len(accounts)} vaults is ₹{total_bal:,.2f}. All security perimeters nominal."}

@app.get("/")
def root():
    return {"status": "FinCore Engine Online"}