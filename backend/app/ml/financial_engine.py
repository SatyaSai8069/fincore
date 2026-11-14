from datetime import datetime, timedelta, timezone
from decimal import Decimal
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ledger import (
    BankAccount,
    EntryDirection,
    JournalTransaction,
    LedgerEntry,
)
from app.models.loan import Loan, LoanStatus
from app.models.risk import RiskAlert
from app.schemas.intelligence import (
    CashFlowPoint,
    CategoryBreakdownItem,
    FinancialInsightsResponse,
    SavingsGoalPlanResponse,
)
from app.services.ledger_service import quantize_money


def classify_transaction(transaction_type: str, description: str | None, direction: str) -> str:
    text = f"{transaction_type} {description or ''}".lower()
    if direction == EntryDirection.CREDIT.value:
        if "loan" in text:
            return "Loan Disbursement"
        if "salary" in text or "bonus" in text or "deposit" in text:
            return "Income & Deposits"
        return "Incoming Transfers"

    if "emi" in text or "loan" in text:
        return "Loan & EMI Repayments"
    if any(k in text for k in ("rent", "electricity", "bill", "water", "internet", "recharge", "tuition")):
        return "Bills & Education"
    if any(k in text for k in ("food", "swiggy", "zomato", "dining", "cafe")):
        return "Food & Dining"
    if any(k in text for k in ("shopping", "amazon", "flipkart", "store")):
        return "Shopping & Retail"
    if "withdraw" in text or "atm" in text:
        return "Cash Withdrawals"
    return "Peer & Merchant Transfers"


class FinancialIntelligenceEngine:
    @classmethod
    async def generate_account_insights(
        cls,
        db: AsyncSession,
        account: BankAccount,
        user_id: str,
    ) -> FinancialInsightsResponse:
        stmt = (
            select(LedgerEntry, JournalTransaction)
            .join(JournalTransaction, LedgerEntry.journal_id == JournalTransaction.id)
            .where(LedgerEntry.account_id == account.id)
            .order_by(LedgerEntry.created_at.asc())
        )
        rows = (await db.execute(stmt)).all()

        records = []
        for entry, journal in rows:
            records.append(
                {
                    "created_at": entry.created_at,
                    "direction": entry.direction.value,
                    "amount": float(entry.amount),
                    "balance_after": float(entry.balance_after),
                    "category": classify_transaction(
                        journal.transaction_type,
                        journal.description,
                        entry.direction.value,
                    ),
                }
            )

        if not records:
            return FinancialInsightsResponse(
                account_number=account.account_number,
                currency=account.currency,
                current_balance=account.available_balance,
                total_inflow=Decimal("0.0000"),
                total_outflow=Decimal("0.0000"),
                net_cash_flow=Decimal("0.0000"),
                savings_rate_percent=0.0,
                financial_health_score=65,
                health_grade="B",
                spending_by_category=[],
                thirty_day_forecast=[],
                recommendations=[
                    "Fund your account to unlock personalized ML cash-flow forecasts."
                ],
            )

        df = pd.DataFrame(records)
        inflow_val = float(df[df["direction"] == "CREDIT"]["amount"].sum())
        outflow_val = float(df[df["direction"] == "DEBIT"]["amount"].sum())
        net_flow_val = inflow_val - outflow_val
        savings_rate = (
            round(max(0.0, (net_flow_val / inflow_val) * 100.0), 2)
            if inflow_val > 0
            else 0.0
        )

        # Category breakdown for outgoing (DEBIT) transactions
        debit_df = df[df["direction"] == "DEBIT"]
        categories: list[CategoryBreakdownItem] = []
        if not debit_df.empty and outflow_val > 0:
            grouped = (
                debit_df.groupby("category", as_index=False)
                .agg(transaction_count=("amount", "count"), total_amount=("amount", "sum"))
                .sort_values(by="total_amount", ascending=False)
            )
            for _, row in grouped.iterrows():
                amt = quantize_money(Decimal(str(row["total_amount"])))
                share = round((float(row["total_amount"]) / outflow_val) * 100.0, 2)
                categories.append(
                    CategoryBreakdownItem(
                        category=str(row["category"]),
                        transaction_count=int(row["transaction_count"]),
                        total_amount=amt,
                        share_percent=share,
                    )
                )

        # Linear Regression trend over ledger balance checkpoints -> 30-day forecast
        y_vals = df["balance_after"].to_numpy(dtype=float)
        x_vals = np.arange(len(y_vals), dtype=float).reshape(-1, 1)

        if len(y_vals) >= 2:
            model = LinearRegression()
            model.fit(x_vals, y_vals)
            step_slope = float(model.coef_[0]) * 0.25
        else:
            step_slope = 0.0

        current_bal_float = float(account.available_balance)
        now = datetime.now(timezone.utc)
        forecast_points: list[CashFlowPoint] = []
        for day_offset in (7, 14, 21, 30):
            projected = max(0.0, current_bal_float + step_slope * (day_offset / 7.0))
            forecast_points.append(
                CashFlowPoint(
                    day_offset=day_offset,
                    date_label=(now + timedelta(days=day_offset)).strftime("%Y-%m-%d"),
                    projected_balance=quantize_money(Decimal(str(projected))),
                )
            )

        # Fetch active loans & unresolved risk alerts to compute Financial Health Score
        loan_res = await db.execute(
            select(Loan).where(Loan.user_id == user_id, Loan.status == LoanStatus.ACTIVE)
        )
        active_loans = list(loan_res.scalars().all())
        total_debt = sum(float(l.outstanding_principal) for l in active_loans)

        alert_res = await db.execute(
            select(RiskAlert).where(
                RiskAlert.user_id == user_id, RiskAlert.is_resolved.is_(False)
            )
        )
        unresolved_alerts = len(list(alert_res.scalars().all()))

        score = 50
        score += min(25, int(savings_rate * 0.5))
        if current_bal_float >= 10000:
            score += 15
        elif current_bal_float > 0:
            score += 8
        if total_debt > current_bal_float * 2 and current_bal_float > 0:
            score -= 10
        score -= min(15, unresolved_alerts * 5)
        score = max(10, min(100, score))

        if score >= 85:
            grade = "A+"
        elif score >= 75:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 45:
            grade = "C"
        else:
            grade = "D"

        recommendations: list[str] = []
        if savings_rate < 20.0:
            recommendations.append(
                "Automate a recurring monthly transfer of at least 20% of inflows into Savings."
            )
        else:
            recommendations.append(
                f"Strong savings discipline ({savings_rate}% net retention); consider laddering surplus into higher-yield instruments."
            )
        if active_loans:
            recommendations.append(
                "Maintain on-time EMI auto-debits to keep credit utilization and repayment health optimal."
            )
        if unresolved_alerts > 0:
            recommendations.append(
                f"Review {unresolved_alerts} flagged high-value/velocity risk alert(s) in your Security Center."
            )

        return FinancialInsightsResponse(
            account_number=account.account_number,
            currency=account.currency,
            current_balance=account.available_balance,
            total_inflow=quantize_money(Decimal(str(inflow_val))),
            total_outflow=quantize_money(Decimal(str(outflow_val))),
            net_cash_flow=quantize_money(Decimal(str(net_flow_val))),
            savings_rate_percent=savings_rate,
            financial_health_score=score,
            health_grade=grade,
            spending_by_category=categories,
            thirty_day_forecast=forecast_points,
            recommendations=recommendations,
        )

    @staticmethod
    def compute_savings_goal_plan(
        account: BankAccount,
        goal_name: str,
        target_amount: Decimal,
        months_to_goal: int,
    ) -> SavingsGoalPlanResponse:
        target = quantize_money(target_amount)
        current = account.available_balance
        shortfall = quantize_money(max(Decimal("0.0000"), target - current))

        annual_rate = account.interest_rate_annual
        monthly_rate = float(annual_rate) / 12.0
        n = months_to_goal

        if shortfall == Decimal("0.0000"):
            monthly_req = Decimal("0.0000")
            interest_earned = quantize_money(
                current * annual_rate * (Decimal(n) / Decimal("12"))
            )
            status_label = "GOAL_ALREADY_FUNDED"
        else:
            fv_current = float(current) * ((1.0 + monthly_rate) ** n)
            remaining_target = max(0.0, float(target) - fv_current)
            if monthly_rate > 0:
                annuity_factor = (((1.0 + monthly_rate) ** n) - 1.0) / monthly_rate
                pmt = remaining_target / annuity_factor
            else:
                pmt = remaining_target / n

            monthly_req = quantize_money(Decimal(str(pmt)))
            total_contributed = float(current) + (float(monthly_req) * n)
            interest_earned = quantize_money(
                Decimal(str(max(0.0, float(target) - total_contributed)))
            )
            status_label = "ON_TRACK_PLAN_READY"

        return SavingsGoalPlanResponse(
            goal_name=goal_name,
            currency=account.currency,
            current_account_balance=current,
            target_amount=target,
            shortfall_amount=shortfall,
            months_to_goal=months_to_goal,
            required_monthly_contribution=monthly_req,
            expected_annual_yield_percent=round(float(annual_rate) * 100.0, 2),
            projected_interest_earned=interest_earned,
            feasibility_status=status_label,
        )