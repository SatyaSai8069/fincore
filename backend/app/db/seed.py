import asyncio
from decimal import Decimal
from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, Base, engine
from app.models.beneficiary import Beneficiary
from app.models.ledger import AccountType, CurrencyCode
from app.models.loan import LoanType
from app.models.user import KYCStatus, User, UserRole
from app.services.ledger_service import LedgerService
from app.services.loan_risk_service import LoanService, RiskEngineService
from app.services.transaction_service import TransactionService


async def seed_demo_data() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == "surya@finora.io"))
        ).scalar_one_or_none()
        if existing:
            print("Demo data already seeded.")
            return

        # 1. Create Admin & Two Customers
        admin = User(
            customer_code="FIN-ADM00001",
            email="admin@finora.io",
            full_name="FINORA Chief Risk Officer",
            phone_number="+919800000000",
            hashed_password=hash_password("Admin@1234"),
            role=UserRole.ADMIN,
            kyc_status=KYCStatus.VERIFIED,
            kyc_document_ref="KYC-ADMIN-001",
        )
        surya = User(
            customer_code="FIN-USR10001",
            email="surya@finora.io",
            full_name="Surya Bareddy",
            phone_number="+919876543210",
            hashed_password=hash_password("Finora@1234"),
            role=UserRole.CUSTOMER,
            kyc_status=KYCStatus.VERIFIED,
            kyc_document_ref="KYC-AADHAAR-8821",
        )
        anita = User(
            customer_code="FIN-USR10002",
            email="anita@finora.io",
            full_name="Anita Rao",
            phone_number="+919876543211",
            hashed_password=hash_password("Finora@1234"),
            role=UserRole.CUSTOMER,
            kyc_status=KYCStatus.VERIFIED,
            kyc_document_ref="KYC-PAN-4419",
        )
        db.add_all([admin, surya, anita])
        await db.flush()

        # 2. Open Multi-Currency Accounts
        surya_inr = await LedgerService.create_customer_account(
            db,
            user_id=surya.id,
            account_type=AccountType.SAVINGS,
            currency=CurrencyCode.INR,
            initial_deposit=Decimal("85000.00"),
            nickname="Primary Wealth Savings",
        )
        surya_usd = await LedgerService.create_customer_account(
            db,
            user_id=surya.id,
            account_type=AccountType.CURRENT,
            currency=CurrencyCode.USD,
            initial_deposit=Decimal("1200.00"),
            nickname="Global USD Treasury",
        )
        anita_inr = await LedgerService.create_customer_account(
            db,
            user_id=anita.id,
            account_type=AccountType.SAVINGS,
            currency=CurrencyCode.INR,
            initial_deposit=Decimal("32000.00"),
            nickname="Anita Daily Savings",
        )

        # 3. Realistic Transaction History
        await TransactionService.deposit(
            db, surya_inr, Decimal("45000.00"), surya.id, "Tech Internship Stipend & Bonus"
        )
        await TransactionService.withdraw(
            db, surya_inr, Decimal("4200.00"), surya.id, "Electricity & Fiber Internet Bill"
        )
        await TransactionService.withdraw(
            db, surya_inr, Decimal("2850.00"), surya.id, "Swiggy & Zomato Dining"
        )
        await TransactionService.withdraw(
            db, surya_inr, Decimal("6400.00"), surya.id, "Amazon Electronics Store"
        )
        await TransactionService.transfer(
            db, surya_inr, anita_inr, Decimal("8500.00"), surya.id, "Shared Research Hardware"
        )
        await TransactionService.transfer(
            db, surya_inr, surya_usd, Decimal("16800.00"), surya.id, "USD Treasury Allocation"
        )

        # 4. Beneficiary
        db.add(
            Beneficiary(
                owner_user_id=surya.id,
                beneficiary_account_number=anita_inr.account_number,
                beneficiary_name=anita.full_name,
                nickname="Anita Research Partner",
                daily_transfer_limit=Decimal("200000.0000"),
            )
        )

        # 5. Active Loan + 1 Paid EMI
        loan = await LoanService.originate_and_disburse_loan(
            db,
            user_id=surya.id,
            account=surya_inr,
            loan_type=LoanType.EDUCATION,
            principal_amount=Decimal("150000.00"),
            tenure_months=12,
            purpose="Data Science & Cloud Certification Lab",
        )
        await LoanService.pay_next_emi(db, loan, surya_inr, surya.id)

        # 6. Risk Alert Sample
        await RiskEngineService.evaluate_transaction(
            db,
            user_id=surya.id,
            account_number=surya_inr.account_number,
            amount=Decimal("275000.00"),
            transaction_reference="TXN-DEMO-FLAG01",
        )

        await db.commit()
        print("FINORA demo dataset seeded successfully!")
        print("Customer Login -> surya@finora.io / Finora@1234")
        print("Admin Login    -> admin@finora.io / Admin@1234")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())