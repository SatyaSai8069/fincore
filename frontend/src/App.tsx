import React, { useEffect, useState } from 'react';
import {
    Activity,
    AlertTriangle,
    ArrowDownLeft,
    ArrowRightLeft,
    ArrowUpRight,
    BrainCircuit,
    Building2,
    CheckCircle2,
    CreditCard,
    Landmark,
    LogOut,
    Plus,
    RefreshCw,
    ShieldCheck,
    Sparkles,
    TrendingUp,
    Wallet,
} from 'lucide-react';
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
import api from './api/client';
import type {
    AdminOverview,
    BankAccount,
    FinancialInsights,
    LoanItem,
    RiskAlertItem,
    SavingsGoalPlan,
    StatementLine,
    UserProfile,
} from './types/banking';

type TabKey = 'overview' | 'payments' | 'loans' | 'intelligence' | 'security';

const CURRENCY_SYMBOLS: Record<string, string> = {
    INR: '₹',
    USD: '$',
    EUR: '€',
    GBP: '£',
};

function formatMoney(val: string | number, currency = 'INR'): string {
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (Number.isNaN(num)) return `${CURRENCY_SYMBOLS[currency] || ''}0.00`;
    return `${CURRENCY_SYMBOLS[currency] || currency + ' '}${num.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

export default function App() {
    const [token, setToken] = useState<string | null>(localStorage.getItem('finora_token'));
    const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
    const [email, setEmail] = useState('surya@finora.io');
    const [password, setPassword] = useState('Finora@1234');
    const [fullName, setFullName] = useState('');
    const [authError, setAuthError] = useState('');
    const [loading, setLoading] = useState(false);

    const [user, setUser] = useState<UserProfile | null>(null);
    const [accounts, setAccounts] = useState<BankAccount[]>([]);
    const [selectedAccNo, setSelectedAccNo] = useState<string>('');
    const [statement, setStatement] = useState<StatementLine[]>([]);
    const [loans, setLoans] = useState<LoanItem[]>([]);
    const [riskAlerts, setRiskAlerts] = useState<RiskAlertItem[]>([]);
    const [insights, setInsights] = useState<FinancialInsights | null>(null);
    const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);

    const [activeTab, setActiveTab] = useState<TabKey>('overview');
    const [banner, setBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

    const [newAccType, setNewAccType] = useState<'SAVINGS' | 'CURRENT'>('SAVINGS');
    const [newAccCurrency, setNewAccCurrency] = useState<'INR' | 'USD' | 'EUR' | 'GBP'>('INR');
    const [newAccDeposit, setNewAccDeposit] = useState('25000');
    const [newAccNick, setNewAccNick] = useState('');

    const [txMode, setTxMode] = useState<'DEPOSIT' | 'WITHDRAW' | 'TRANSFER'>('TRANSFER');
    const [txAmount, setTxAmount] = useState('5000');
    const [txDestAcc, setTxDestAcc] = useState('');
    const [txDesc, setTxDesc] = useState('');

    const [loanType, setLoanType] = useState<'PERSONAL' | 'HOME' | 'EDUCATION' | 'BUSINESS'>('EDUCATION');
    const [loanPrincipal, setLoanPrincipal] = useState('100000');
    const [loanTenure, setLoanTenure] = useState('12');
    const [loanPurpose, setLoanPurpose] = useState('Cloud & AI Research Infrastructure');

    const [goalName, setGoalName] = useState('Emergency Wealth Reserve');
    const [goalTarget, setGoalTarget] = useState('300000');
    const [goalMonths, setGoalMonths] = useState('12');
    const [goalPlan, setGoalPlan] = useState<SavingsGoalPlan | null>(null);

    const selectedAccount = accounts.find((a) => a.account_number === selectedAccNo) || accounts[0];

    const notify = (type: 'ok' | 'err', text: string) => {
        setBanner({ type, text });
        setTimeout(() => setBanner(null), 5000);
    };

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setAuthError('');
        setLoading(true);
        try {
            if (authMode === 'register') {
                await api.post('/auth/register', {
                    email,
                    full_name: fullName || 'FINORA Client',
                    password,
                });
            }
            const res = await api.post('/auth/login', { email, password });
            const accessToken = res.data.access_token;
            localStorage.setItem('finora_token', accessToken);
            setToken(accessToken);
        } catch (err: any) {
            setAuthError(err?.response?.data?.detail || 'Authentication failed. Check credentials.');
        } finally {
            setLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('finora_token');
        setToken(null);
        setUser(null);
        setAccounts([]);
        setInsights(null);
    };

    const loadDashboard = async () => {
        if (!token) return;
        try {
            const [meRes, accRes, loansRes, riskRes] = await Promise.all([
                api.get('/auth/me'),
                api.get('/accounts'),
                api.get('/loans'),
                api.get('/risk/alerts'),
            ]);
            setUser(meRes.data);
            const accList: BankAccount[] = accRes.data;
            setAccounts(accList);
            setLoans(loansRes.data);
            setRiskAlerts(riskRes.data);

            const activeNumber =
                selectedAccNo && accList.some((a) => a.account_number === selectedAccNo)
                    ? selectedAccNo
                    : accList[0]?.account_number || '';
            setSelectedAccNo(activeNumber);

            if (meRes.data.role === 'ADMIN' || meRes.data.role === 'AUDITOR') {
                const admRes = await api.get('/admin/overview');
                setAdminOverview(admRes.data);
            } else {
                setAdminOverview(null);
            }
        } catch {
            handleLogout();
        }
    };

    const loadAccountDetails = async (accNo: string) => {
        if (!accNo) return;
        try {
            const [stmtRes, insRes] = await Promise.all([
                api.get(`/transactions/statement/${accNo}?limit=20`),
                api.get(`/intelligence/insights/${accNo}`),
            ]);
            setStatement(stmtRes.data.entries || []);
            setInsights(insRes.data);
        } catch {
            // ignore if account has no entries yet
        }
    };

    useEffect(() => {
        loadDashboard();
    }, [token]);

    useEffect(() => {
        if (selectedAccNo) {
            loadAccountDetails(selectedAccNo);
        }
    }, [selectedAccNo, accounts]);

    const handleCreateAccount = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await api.post('/accounts', {
                account_type: newAccType,
                currency: newAccCurrency,
                initial_deposit: newAccDeposit,
                nickname: newAccNick || `${newAccCurrency} ${newAccType}`,
            });
            notify('ok', `Opened ${res.data.account_number} (${res.data.currency})`);
            setNewAccNick('');
            await loadDashboard();
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'Could not open account');
        }
    };

    const handleExecuteTransaction = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedAccount) return;
        try {
            if (txMode === 'DEPOSIT') {
                await api.post('/transactions/deposit', {
                    account_number: selectedAccount.account_number,
                    amount: txAmount,
                    description: txDesc || 'Direct Digital Deposit',
                });
                notify('ok', `Deposited ${formatMoney(txAmount, selectedAccount.currency)}`);
            } else if (txMode === 'WITHDRAW') {
                await api.post('/transactions/withdraw', {
                    account_number: selectedAccount.account_number,
                    amount: txAmount,
                    description: txDesc || 'Account Withdrawal',
                });
                notify('ok', `Withdrew ${formatMoney(txAmount, selectedAccount.currency)}`);
            } else {
                await api.post('/transactions/transfer', {
                    source_account_number: selectedAccount.account_number,
                    destination_account_number: txDestAcc.trim(),
                    amount: txAmount,
                    description: txDesc || 'FINORA Instant Transfer',
                });
                notify('ok', `Transferred ${formatMoney(txAmount, selectedAccount.currency)} to ${txDestAcc}`);
            }
            setTxDesc('');
            await loadDashboard();
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'Transaction rejected');
        }
    };

    const handleApplyLoan = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedAccount) return;
        try {
            const res = await api.post('/loans/apply', {
                disbursement_account_number: selectedAccount.account_number,
                loan_type: loanType,
                principal_amount: loanPrincipal,
                tenure_months: Number(loanTenure),
                purpose: loanPurpose,
            });
            notify('ok', `Loan ${res.data.loan_number} approved & disbursed instantly!`);
            await loadDashboard();
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'Loan origination failed');
        }
    };

    const handlePayEmi = async (loanNumber: string) => {
        try {
            const res = await api.post(`/loans/${loanNumber}/pay-emi`);
            notify('ok', `Paid Installment #${res.data.installment_number} for ${loanNumber}`);
            await loadDashboard();
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'EMI payment failed');
        }
    };

    const handlePlanGoal = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedAccount) return;
        try {
            const res = await api.post('/intelligence/savings-goal', {
                account_number: selectedAccount.account_number,
                goal_name: goalName,
                target_amount: goalTarget,
                months_to_goal: Number(goalMonths),
            });
            setGoalPlan(res.data);
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'Could not compute savings goal');
        }
    };

    const handleResolveAlert = async (alertId: string) => {
        try {
            await api.patch(`/risk/alerts/${alertId}/resolve`);
            notify('ok', 'Risk alert marked resolved');
            await loadDashboard();
        } catch (err: any) {
            notify('err', err?.response?.data?.detail || 'Admin/Auditor role required');
        }
    };

    if (!token) {
        return (
            <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4 relative overflow-hidden">
                <div className="absolute -top-40 -left-40 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

                <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-slate-950 font-bold shadow-lg">
                            <Landmark className="w-6 h-6" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight text-white">FINORA</h1>
                            <p className="text-xs text-slate-400">Digital Banking & Financial Intelligence</p>
                        </div>
                    </div>

                    <div className="flex bg-slate-950 p-1 rounded-xl mb-6 border border-slate-800">
                        <button
                            type="button"
                            onClick={() => setAuthMode('login')}
                            className={`flex-1 py-2 text-sm font-medium rounded-lg transition ${authMode === 'login'
                                    ? 'bg-emerald-500 text-slate-950 font-semibold'
                                    : 'text-slate-400 hover:text-white'
                                }`}
                        >
                            Sign In
                        </button>
                        <button
                            type="button"
                            onClick={() => setAuthMode('register')}
                            className={`flex-1 py-2 text-sm font-medium rounded-lg transition ${authMode === 'register'
                                    ? 'bg-emerald-500 text-slate-950 font-semibold'
                                    : 'text-slate-400 hover:text-white'
                                }`}
                        >
                            Open Account
                        </button>
                    </div>

                    {authError && (
                        <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
                            {authError}
                        </div>
                    )}

                    <form onSubmit={handleAuth} className="space-y-4">
                        {authMode === 'register' && (
                            <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">Full Legal Name</label>
                                <input
                                    type="text"
                                    required
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                    placeholder="Surya Bareddy"
                                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm focus:outline-none focus:border-emerald-500"
                                />
                            </div>
                        )}

                        <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                            <input
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm focus:outline-none focus:border-emerald-500"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">Password</label>
                            <input
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm focus:outline-none focus:border-emerald-500"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-slate-950 font-semibold text-sm hover:opacity-95 transition cursor-pointer"
                        >
                            {loading
                                ? 'Authenticating...'
                                : authMode === 'login'
                                    ? 'Access Secure Vault'
                                    : 'Create FINORA Identity'}
                        </button>
                    </form>

                    <div className="mt-6 pt-5 border-t border-slate-800">
                        <p className="text-xs text-slate-400 mb-2">Instant Demo Credentials (Run Seeder First):</p>
                        <div className="grid grid-cols-2 gap-2">
                            <button
                                type="button"
                                onClick={() => {
                                    setAuthMode('login');
                                    setEmail('surya@finora.io');
                                    setPassword('Finora@1234');
                                }}
                                className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 hover:border-emerald-500/50 text-left text-xs transition"
                            >
                                <span className="block font-semibold text-emerald-400">Customer Demo</span>
                                <span className="text-slate-400">surya@finora.io</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    setAuthMode('login');
                                    setEmail('admin@finora.io');
                                    setPassword('Admin@1234');
                                }}
                                className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500/50 text-left text-xs transition"
                            >
                                <span className="block font-semibold text-cyan-400">CRO / Admin</span>
                                <span className="text-slate-400">admin@finora.io</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
            <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur sticky top-0 z-30">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-slate-950 font-bold">
                            <Landmark className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="font-bold tracking-tight text-white text-lg">FINORA</span>
                                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                    Core Ledger v1.0
                                </span>
                            </div>
                        </div>
                    </div>

                    <nav className="hidden md:flex items-center gap-1 bg-slate-950/90 p-1 rounded-xl border border-slate-800">
                        {[
                            { id: 'overview', label: 'Accounts & Ledger', icon: Wallet },
                            { id: 'payments', label: 'Payments & FX', icon: ArrowRightLeft },
                            { id: 'loans', label: 'Loans & EMI', icon: CreditCard },
                            { id: 'intelligence', label: 'AI Intelligence', icon: BrainCircuit },
                            { id: 'security', label: 'Risk & Governance', icon: ShieldCheck },
                        ].map((item) => {
                            const Icon = item.icon;
                            return (
                                <button
                                    key={item.id}
                                    onClick={() => setActiveTab(item.id as TabKey)}
                                    className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${activeTab === item.id
                                            ? 'bg-emerald-500 text-slate-950 font-semibold shadow'
                                            : 'text-slate-400 hover:text-white'
                                        }`}
                                >
                                    <Icon className="w-3.5 h-3.5" />
                                    {item.label}
                                </button>
                            );
                        })}
                    </nav>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={loadDashboard}
                            title="Refresh Ledger"
                            className="p-2 rounded-lg bg-slate-800/70 hover:bg-slate-800 text-slate-300 transition"
                        >
                            <RefreshCw className="w-4 h-4" />
                        </button>
                        <div className="text-right hidden sm:block">
                            <p className="text-xs font-semibold text-white">{user?.full_name}</p>
                            <p className="text-[11px] text-slate-400">
                                {user?.customer_code} • <span className="text-emerald-400">{user?.role}</span>
                            </p>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition"
                        >
                            <LogOut className="w-3.5 h-3.5" />
                            Exit
                        </button>
                    </div>
                </div>
            </header>

            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
                {banner && (
                    <div
                        className={`p-3.5 rounded-xl border text-sm flex items-center justify-between ${banner.type === 'ok'
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                                : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                            }`}
                    >
                        <span>{banner.text}</span>
                    </div>
                )}

                <section className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {accounts.map((acc) => {
                        const active = acc.account_number === selectedAccount?.account_number;
                        return (
                            <div
                                key={acc.id}
                                onClick={() => setSelectedAccNo(acc.account_number)}
                                className={`p-5 rounded-2xl border transition cursor-pointer ${active
                                        ? 'bg-gradient-to-br from-slate-900 to-emerald-950/40 border-emerald-500/60 shadow-lg shadow-emerald-950/30'
                                        : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                                    }`}
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded-md bg-slate-800 text-slate-300">
                                        {acc.currency} • {acc.account_type}
                                    </span>
                                    <span className="text-[11px] font-mono text-slate-400">{acc.account_number}</span>
                                </div>
                                <p className="text-2xl font-bold text-white tracking-tight">
                                    {formatMoney(acc.available_balance, acc.currency)}
                                </p>
                                <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                                    <span>{acc.nickname || 'Primary Account'}</span>
                                    <span className="text-emerald-400">
                                        {(parseFloat(acc.interest_rate_annual) * 100).toFixed(2)}% APY
                                    </span>
                                </div>
                            </div>
                        );
                    })}

                    <form
                        onSubmit={handleCreateAccount}
                        className="p-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-700 flex flex-col justify-between gap-2"
                    >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                            <Plus className="w-4 h-4 text-emerald-400" /> Open Multi-Currency Account
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <select
                                value={newAccType}
                                onChange={(e) => setNewAccType(e.target.value as any)}
                                className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs"
                            >
                                <option value="SAVINGS">SAVINGS</option>
                                <option value="CURRENT">CURRENT</option>
                            </select>
                            <select
                                value={newAccCurrency}
                                onChange={(e) => setNewAccCurrency(e.target.value as any)}
                                className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs"
                            >
                                <option value="INR">INR (₹)</option>
                                <option value="USD">USD ($)</option>
                                <option value="EUR">EUR (€)</option>
                                <option value="GBP">GBP (£)</option>
                            </select>
                        </div>
                        <div className="flex gap-2">
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={newAccDeposit}
                                onChange={(e) => setNewAccDeposit(e.target.value)}
                                placeholder="Initial deposit"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs"
                            />
                            <button
                                type="submit"
                                className="px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-semibold text-xs hover:bg-emerald-400 transition shrink-0"
                            >
                                Open
                            </button>
                        </div>
                    </form>
                </section>

                {activeTab === 'overview' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h2 className="text-base font-semibold text-white">Immutable Double-Entry Statement</h2>
                                    <p className="text-xs text-slate-400">
                                        Account {selectedAccount?.account_number || '—'} • Real-time balanced ledger entries
                                    </p>
                                </div>
                                {insights && (
                                    <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-right">
                                        <span className="text-[11px] text-emerald-300 block">Health Score</span>
                                        <span className="text-sm font-bold text-white">
                                            {insights.financial_health_score}/100 ({insights.health_grade})
                                        </span>
                                    </div>
                                )}
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-slate-800 text-[11px] uppercase text-slate-400">
                                            <th className="py-2.5">Reference</th>
                                            <th className="py-2.5">Description</th>
                                            <th className="py-2.5">Type</th>
                                            <th className="py-2.5 text-right">Amount</th>
                                            <th className="py-2.5 text-right">Running Balance</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/60 text-xs">
                                        {statement.length === 0 ? (
                                            <tr>
                                                <td colSpan={5} className="py-8 text-center text-slate-500">
                                                    No ledger entries recorded for this account yet.
                                                </td>
                                            </tr>
                                        ) : (
                                            statement.map((row) => (
                                                <tr key={row.entry_id} className="hover:bg-slate-800/30">
                                                    <td className="py-3 font-mono text-slate-300">{row.reference_number}</td>
                                                    <td className="py-3 text-slate-200">{row.description || row.transaction_type}</td>
                                                    <td className="py-3">
                                                        <span
                                                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-medium ${row.direction === 'CREDIT'
                                                                    ? 'bg-emerald-500/15 text-emerald-300'
                                                                    : 'bg-amber-500/15 text-amber-300'
                                                                }`}
                                                        >
                                                            {row.direction === 'CREDIT' ? (
                                                                <ArrowDownLeft className="w-3 h-3" />
                                                            ) : (
                                                                <ArrowUpRight className="w-3 h-3" />
                                                            )}
                                                            {row.direction}
                                                        </span>
                                                    </td>
                                                    <td
                                                        className={`py-3 text-right font-semibold ${row.direction === 'CREDIT' ? 'text-emerald-400' : 'text-slate-200'
                                                            }`}
                                                    >
                                                        {row.direction === 'CREDIT' ? '+' : '-'}
                                                        {formatMoney(row.amount, selectedAccount?.currency)}
                                                    </td>
                                                    <td className="py-3 text-right font-mono text-slate-300">
                                                        {formatMoney(row.balance_after, selectedAccount?.currency)}
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between space-y-5">
                            <div>
                                <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">
                                    <Sparkles className="w-4 h-4" /> AI Financial Snapshot
                                </div>
                                <h3 className="text-lg font-bold text-white mb-4">Cash Flow & Recommendations</h3>

                                {insights && (
                                    <div className="space-y-3">
                                        <div className="grid grid-cols-2 gap-3">
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-[11px] text-slate-400 block">Total Inflow</span>
                                                <span className="text-sm font-bold text-emerald-400">
                                                    {formatMoney(insights.total_inflow, insights.currency)}
                                                </span>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-[11px] text-slate-400 block">Total Outflow</span>
                                                <span className="text-sm font-bold text-rose-400">
                                                    {formatMoney(insights.total_outflow, insights.currency)}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                                            <span className="text-xs text-slate-400">Net Savings Retention</span>
                                            <span className="text-sm font-bold text-cyan-400">
                                                {insights.savings_rate_percent}%
                                            </span>
                                        </div>

                                        <div className="space-y-2 pt-2">
                                            <p className="text-xs font-semibold text-slate-300">Advisory Actions:</p>
                                            {insights.recommendations.map((rec, i) => (
                                                <div
                                                    key={i}
                                                    className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 text-xs text-slate-300 leading-relaxed"
                                                >
                                                    {rec}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <button
                                onClick={() => setActiveTab('intelligence')}
                                className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition"
                            >
                                Open 30-Day ML Forecast & Goal Planner →
                            </button>
                        </div>
                    </div>
                )}

                {activeTab === 'payments' && (
                    <div className="max-w-2xl mx-auto bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
                        <h2 className="text-lg font-bold text-white mb-1">Payments, Deposits & Cross-Currency FX</h2>
                        <p className="text-xs text-slate-400 mb-6">
                            Operating from: <span className="text-emerald-400 font-mono">{selectedAccount?.account_number}</span> ({selectedAccount?.currency})
                        </p>

                        <div className="flex gap-2 mb-6">
                            {(['TRANSFER', 'DEPOSIT', 'WITHDRAW'] as const).map((m) => (
                                <button
                                    key={m}
                                    type="button"
                                    onClick={() => setTxMode(m)}
                                    className={`flex-1 py-2 rounded-xl text-xs font-semibold border transition ${txMode === m
                                            ? 'bg-emerald-500 text-slate-950 border-emerald-500'
                                            : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-white'
                                        }`}
                                >
                                    {m === 'TRANSFER' ? 'P2P / FX Transfer' : m === 'DEPOSIT' ? 'Cash / Wire Deposit' : 'Withdrawal'}
                                </button>
                            ))}
                        </div>

                        <form onSubmit={handleExecuteTransaction} className="space-y-4">
                            {txMode === 'TRANSFER' && (
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1">
                                        Destination Account Number (Supports INR ↔ USD / EUR / GBP auto-FX)
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        value={txDestAcc}
                                        onChange={(e) => setTxDestAcc(e.target.value)}
                                        placeholder="FIN..."
                                        className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm font-mono"
                                    />
                                    {accounts.length > 1 && (
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {accounts
                                                .filter((a) => a.account_number !== selectedAccount?.account_number)
                                                .map((other) => (
                                                    <button
                                                        key={other.id}
                                                        type="button"
                                                        onClick={() => setTxDestAcc(other.account_number)}
                                                        className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300"
                                                    >
                                                        Use my {other.currency} ({other.account_number})
                                                    </button>
                                                ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">
                                    Amount ({selectedAccount?.currency || 'INR'})
                                </label>
                                <input
                                    type="number"
                                    step="0.01"
                                    min="1"
                                    required
                                    value={txAmount}
                                    onChange={(e) => setTxAmount(e.target.value)}
                                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Narration / Reference Note</label>
                                <input
                                    type="text"
                                    value={txDesc}
                                    onChange={(e) => setTxDesc(e.target.value)}
                                    placeholder="e.g., Monthly Tuition, Swiggy Order, USD Allocation"
                                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                />
                            </div>

                            <button
                                type="submit"
                                className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-slate-950 font-bold text-sm hover:opacity-95 transition"
                            >
                                Execute Atomic Ledger Transaction
                            </button>
                        </form>
                    </div>
                )}

                {activeTab === 'loans' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <form
                            onSubmit={handleApplyLoan}
                            className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4 h-fit"
                        >
                            <h2 className="text-base font-bold text-white">Instant Credit Origination</h2>
                            <p className="text-xs text-slate-400">
                                Disburses directly into <span className="text-emerald-400 font-mono">{selectedAccount?.account_number}</span> with full reducing-balance amortization.
                            </p>

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Loan Facility</label>
                                <select
                                    value={loanType}
                                    onChange={(e) => setLoanType(e.target.value as any)}
                                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                >
                                    <option value="HOME">Home Loan (8.50% p.a.)</option>
                                    <option value="EDUCATION">Education Loan (9.25% p.a.)</option>
                                    <option value="BUSINESS">Business Expansion (11.50% p.a.)</option>
                                    <option value="PERSONAL">Personal Credit (13.00% p.a.)</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Principal Amount</label>
                                <input
                                    type="number"
                                    min="1001"
                                    required
                                    value={loanPrincipal}
                                    onChange={(e) => setLoanPrincipal(e.target.value)}
                                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Tenure (Months)</label>
                                <input
                                    type="number"
                                    min="3"
                                    max="360"
                                    required
                                    value={loanTenure}
                                    onChange={(e) => setLoanTenure(e.target.value)}
                                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Purpose</label>
                                <input
                                    type="text"
                                    value={loanPurpose}
                                    onChange={(e) => setLoanPurpose(e.target.value)}
                                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm"
                                />
                            </div>

                            <button
                                type="submit"
                                className="w-full py-2.5 rounded-xl bg-emerald-500 text-slate-950 font-bold text-sm hover:bg-emerald-400 transition"
                            >
                                Approve & Disburse Loan
                            </button>
                        </form>

                        <div className="lg:col-span-2 space-y-4">
                            {loans.length === 0 ? (
                                <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-10 text-center text-slate-400 text-sm">
                                    No active loan facilities. Apply on the left for instant disbursement.
                                </div>
                            ) : (
                                loans.map((loan) => (
                                    <div
                                        key={loan.id}
                                        className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                                    >
                                        <div>
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-mono font-bold text-white">{loan.loan_number}</span>
                                                <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300">
                                                    {loan.loan_type}
                                                </span>
                                                <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
                                                    {loan.status}
                                                </span>
                                            </div>
                                            <p className="text-xs text-slate-400 mb-3">{loan.purpose || 'Standard Credit Facility'}</p>
                                            <div className="flex flex-wrap gap-6 text-xs">
                                                <div>
                                                    <span className="text-slate-400 block">Principal</span>
                                                    <span className="font-semibold text-white">
                                                        {formatMoney(loan.principal_amount, loan.currency)}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 block">Outstanding</span>
                                                    <span className="font-semibold text-amber-300">
                                                        {formatMoney(loan.outstanding_principal, loan.currency)}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 block">Monthly EMI</span>
                                                    <span className="font-semibold text-emerald-400">
                                                        {formatMoney(loan.emi_amount, loan.currency)}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 block">Interest Rate</span>
                                                    <span className="font-semibold text-white">
                                                        {(parseFloat(loan.annual_interest_rate) * 100).toFixed(2)}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        {loan.status === 'ACTIVE' && (
                                            <button
                                                onClick={() => handlePayEmi(loan.loan_number)}
                                                className="px-4 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shrink-0 transition"
                                            >
                                                Pay Next EMI
                                            </button>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'intelligence' && insights && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
                                <div className="flex items-center justify-between mb-4">
                                    <div>
                                        <h3 className="text-base font-bold text-white flex items-center gap-2">
                                            <TrendingUp className="w-4 h-4 text-emerald-400" /> 30-Day ML Balance Trajectory
                                        </h3>
                                        <p className="text-xs text-slate-400">Linear regression projection over ledger velocity</p>
                                    </div>
                                </div>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart
                                            data={insights.thirty_day_forecast.map((pt) => ({
                                                date: pt.date_label,
                                                balance: parseFloat(pt.projected_balance),
                                            }))}
                                        >
                                            <defs>
                                                <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                            <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                                            <YAxis stroke="#94a3b8" fontSize={11} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: 12 }}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="balance"
                                                stroke="#10b981"
                                                strokeWidth={2.5}
                                                fill="url(#balGrad)"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
                                <h3 className="text-base font-bold text-white mb-1">Automated Outflow Categorization</h3>
                                <p className="text-xs text-slate-400 mb-4">NLP-classified ledger debits by merchant/purpose</p>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart
                                            data={insights.spending_by_category.map((c) => ({
                                                category: c.category,
                                                amount: parseFloat(c.total_amount),
                                            }))}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                            <XAxis dataKey="category" stroke="#94a3b8" fontSize={10} />
                                            <YAxis stroke="#94a3b8" fontSize={11} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: 12 }}
                                            />
                                            <Bar dataKey="amount" fill="#06b6d4" radius={[6, 6, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <form onSubmit={handlePlanGoal} className="space-y-4">
                                <h3 className="text-base font-bold text-white">Compound Yield Savings Goal Optimizer</h3>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-1">Goal Title</label>
                                        <input
                                            type="text"
                                            required
                                            value={goalName}
                                            onChange={(e) => setGoalName(e.target.value)}
                                            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-1">Target Amount</label>
                                        <input
                                            type="number"
                                            required
                                            value={goalTarget}
                                            onChange={(e) => setGoalTarget(e.target.value)}
                                            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-1">Horizon (Months)</label>
                                        <input
                                            type="number"
                                            min="1"
                                            max="240"
                                            required
                                            value={goalMonths}
                                            onChange={(e) => setGoalMonths(e.target.value)}
                                            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                                        />
                                    </div>
                                </div>
                                <button
                                    type="submit"
                                    className="px-5 py-2.5 rounded-xl bg-emerald-500 text-slate-950 font-bold text-xs hover:bg-emerald-400 transition"
                                >
                                    Compute Optimal Monthly Contribution
                                </button>
                            </form>

                            {goalPlan && (
                                <div className="p-5 rounded-2xl bg-slate-950 border border-emerald-500/30 flex flex-col justify-center">
                                    <span className="text-xs text-emerald-400 font-semibold">{goalPlan.goal_name}</span>
                                    <p className="text-2xl font-bold text-white mt-1">
                                        {formatMoney(goalPlan.required_monthly_contribution, goalPlan.currency)}{' '}
                                        <span className="text-xs font-normal text-slate-400">/ month required</span>
                                    </p>
                                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                                        <div>
                                            <span className="text-slate-400 block">Shortfall</span>
                                            <span className="text-white font-semibold">
                                                {formatMoney(goalPlan.shortfall_amount, goalPlan.currency)}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-400 block">APY Yield</span>
                                            <span className="text-cyan-400 font-semibold">
                                                {goalPlan.expected_annual_yield_percent}%
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-400 block">Interest Earned</span>
                                            <span className="text-emerald-400 font-semibold">
                                                {formatMoney(goalPlan.projected_interest_earned, goalPlan.currency)}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'security' && (
                    <div className="space-y-6">
                        {adminOverview && (
                            <div className="bg-slate-900/70 border border-cyan-500/30 rounded-2xl p-6">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                                        <Building2 className="w-4 h-4 text-cyan-400" /> Bank-Wide Executive Governance
                                    </h2>
                                    <span
                                        className={`px-3 py-1 rounded-full text-xs font-semibold ${adminOverview.double_entry_balanced
                                                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                                : 'bg-rose-500/20 text-rose-300'
                                            }`}
                                    >
                                        {adminOverview.double_entry_balanced
                                            ? '✓ Global Ledger Debits == Credits Verified'
                                            : 'Ledger Imbalance Detected'}
                                    </span>
                                </div>

                                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                                        <span className="text-slate-400 block">Total Customers</span>
                                        <span className="text-xl font-bold text-white">{adminOverview.total_customers}</span>
                                    </div>
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                                        <span className="text-slate-400 block">Active Accounts</span>
                                        <span className="text-xl font-bold text-white">{adminOverview.active_bank_accounts}</span>
                                    </div>
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                                        <span className="text-slate-400 block">Journal Entries</span>
                                        <span className="text-xl font-bold text-cyan-400">
                                            {adminOverview.total_journal_transactions}
                                        </span>
                                    </div>
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                                        <span className="text-slate-400 block">Active Loans</span>
                                        <span className="text-xl font-bold text-white">{adminOverview.active_loans_count}</span>
                                    </div>
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                                        <span className="text-slate-400 block">Open Risk Alerts</span>
                                        <span className="text-xl font-bold text-amber-400">
                                            {adminOverview.unresolved_risk_alerts}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
                            <h3 className="text-base font-bold text-white flex items-center gap-2 mb-4">
                                <Activity className="w-4 h-4 text-amber-400" /> Real-Time Fraud & AML Risk Alerts
                            </h3>

                            {riskAlerts.length === 0 ? (
                                <p className="text-xs text-slate-400">No risk alerts flagged on your profile.</p>
                            ) : (
                                <div className="space-y-3">
                                    {riskAlerts.map((al) => (
                                        <div
                                            key={al.id}
                                            className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                                        >
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                                                    <span className="text-xs font-bold text-white">{al.rule_triggered}</span>
                                                    <span className="text-[11px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300">
                                                        {al.severity} (Score {al.risk_score}/100)
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-400 mt-1">
                                                    Account {al.account_number} • Amount {al.amount} • {al.details}
                                                </p>
                                            </div>

                                            {al.is_resolved ? (
                                                <span className="inline-flex items-center gap-1 text-xs text-emerald-400 font-semibold">
                                                    <CheckCircle2 className="w-4 h-4" /> Resolved
                                                </span>
                                            ) : (
                                                (user?.role === 'ADMIN' || user?.role === 'AUDITOR') && (
                                                    <button
                                                        onClick={() => handleResolveAlert(al.id)}
                                                        className="px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-semibold text-xs"
                                                    >
                                                        Mark Resolved
                                                    </button>
                                                )
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}