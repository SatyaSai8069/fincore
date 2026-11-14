export interface UserProfile {
    id: string;
    customer_code: string;
    email: string;
    full_name: string;
    phone_number?: string;
    role: 'CUSTOMER' | 'AUDITOR' | 'ADMIN';
    kyc_status: 'PENDING' | 'VERIFIED' | 'REJECTED';
    is_active: boolean;
    mfa_enabled: boolean;
    created_at: string;
}

export interface BankAccount {
    id: string;
    account_number: string;
    account_type: 'SAVINGS' | 'CURRENT' | 'LOAN';
    currency: 'INR' | 'USD' | 'EUR' | 'GBP';
    status: 'ACTIVE' | 'FROZEN' | 'CLOSED';
    interest_rate_annual: string;
    available_balance: string;
    ledger_balance: string;
    nickname?: string;
    created_at: string;
}

export interface StatementLine {
    entry_id: string;
    reference_number: string;
    transaction_type: string;
    direction: 'DEBIT' | 'CREDIT';
    amount: string;
    balance_after: string;
    description?: string;
    created_at: string;
}

export interface LoanItem {
    id: string;
    loan_number: string;
    loan_type: 'PERSONAL' | 'HOME' | 'EDUCATION' | 'BUSINESS';
    currency: 'INR' | 'USD' | 'EUR' | 'GBP';
    principal_amount: string;
    annual_interest_rate: string;
    tenure_months: number;
    emi_amount: string;
    outstanding_principal: string;
    status: 'PENDING' | 'ACTIVE' | 'CLOSED' | 'REJECTED';
    purpose?: string;
    created_at: string;
}

export interface RiskAlertItem {
    id: string;
    user_id: string;
    account_number: string;
    transaction_reference?: string;
    risk_score: number;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    rule_triggered: string;
    amount: string;
    details: string;
    is_resolved: boolean;
    created_at: string;
}

export interface FinancialInsights {
    account_number: string;
    currency: 'INR' | 'USD' | 'EUR' | 'GBP';
    current_balance: string;
    total_inflow: string;
    total_outflow: string;
    net_cash_flow: string;
    savings_rate_percent: number;
    financial_health_score: number;
    health_grade: string;
    spending_by_category: {
        category: string;
        transaction_count: number;
        total_amount: string;
        share_percent: number;
    }[];
    thirty_day_forecast: {
        day_offset: number;
        date_label: string;
        projected_balance: string;
    }[];
    recommendations: string[];
}

export interface SavingsGoalPlan {
    goal_name: string;
    currency: string;
    current_account_balance: string;
    target_amount: string;
    shortfall_amount: string;
    months_to_goal: number;
    required_monthly_contribution: string;
    expected_annual_yield_percent: number;
    projected_interest_earned: string;
    feasibility_status: string;
}

export interface AdminOverview {
    total_customers: number;
    active_bank_accounts: number;
    total_journal_transactions: number;
    active_loans_count: number;
    unresolved_risk_alerts: number;
    total_customer_deposits_by_currency: Record<string, string>;
    double_entry_balanced: boolean;
}