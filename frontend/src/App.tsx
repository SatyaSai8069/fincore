import React, { Component, ErrorInfo, ReactNode, useEffect, useMemo, useState } from 'react';
import {
    Activity, AlertTriangle, ArrowDownLeft, ArrowUpRight, Bot, CheckCircle2,
    Cpu, CreditCard, Globe, History, Landmark, Layers, Lock, Menu, Plus, RefreshCw,
    Send, ShieldAlert, Sliders, Sparkles, Trash2, TrendingUp, Wallet, X, Zap
} from 'lucide-react';
import {
    Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
    ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || "https://fincore-backend-4fi9.onrender.com/api/v1";
const FX_TO_INR: Record<string, number> = { INR: 1, USD: 84.2, EUR: 91.5, GBP: 106.8 };
const CURRENCY_SYMBOL: Record<string, string> = { INR: '₹', USD: '$', EUR: '€', GBP: '£' };

class WorkspaceErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; message: string }> {
    constructor(props: { children: ReactNode }) {
        super(props);
        this.state = { hasError: false, message: '' };
    }
    static getDerivedStateFromError(error: Error) { return { hasError: true, message: error.message }; }
    componentDidCatch(error: Error, info: ErrorInfo) { console.error('Error:', error, info); }
    render() {
        if (this.state.hasError) {
            return (
                <div className="p-8 rounded-3xl bg-slate-900/80 backdrop-blur-2xl border border-rose-500/40 text-slate-100 shadow-2xl">
                    <h3 className="text-lg font-bold text-rose-400 mb-2">Workspace Module Exception</h3>
                    <p className="text-sm text-slate-300 mb-4">{this.state.message || 'Re-establishing stream.'}</p>
                    <button onClick={() => this.setState({ hasError: false, message: '' })} className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-500 font-semibold text-sm shadow-lg hover:scale-105 transition cursor-pointer">
                        Reload Module
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

export default function App() {
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('fincore_token'));
    const [authMode, setAuthMode] = useState<'login' | 'register'>('register');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('Satya Sai Bareddy');
    const [authError, setAuthError] = useState('');

    const [activeTab, setActiveTab] = useState<'accounts' | 'transfer' | 'history' | 'fds' | 'loans' | 'planner' | 'security'>('accounts');
    const [selectedHistoryAccount, setSelectedHistoryAccount] = useState<string>('ALL');
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastSynced, setLastSynced] = useState<string>('Just now');
    const [toast, setToast] = useState<string | null>(null);

    const [accounts, setAccounts] = useState<any[]>([]);
    const [transactions, setTransactions] = useState<any[]>([]);
    const [fds, setFds] = useState<any[]>([]);
    const [loans, setLoans] = useState<any[]>([]);
    const [riskAlerts, setRiskAlerts] = useState<any[]>([]);

    const [fromAcc, setFromAcc] = useState('');
    const [toAcc, setToAcc] = useState('');
    const [txAmount, setTxAmount] = useState('');
    const [txNote, setTxNote] = useState('');
    const [newVaultCurrency, setNewVaultCurrency] = useState('INR');
    const [newVaultType, setNewVaultType] = useState('SAVINGS');
    const [initialDeposit, setInitialDeposit] = useState('5000');

    const [fdAmount, setFdAmount] = useState('25000');
    const [fdMonths, setFdMonths] = useState('12');
    const [loanAmount, setLoanAmount] = useState('200000');
    const [loanTenure, setLoanTenure] = useState('24');

    const [simMonths, setSimMonths] = useState(12);
    const [simMonthlySip, setSimMonthlySip] = useState(25000);
    const [simExpenseCutPct, setSimExpenseCutPct] = useState(15);

    const [rules, setRules] = useState<Array<{ id: string; trigger: number; pct: number; target: string; active: boolean }>>([
        { id: 'r1', trigger: 50000, pct: 20, target: 'High-Yield Reserve Vault', active: true },
    ]);
    const [ruleTrigger, setRuleTrigger] = useState('25000');
    const [rulePct, setRulePct] = useState('15');

    const [chatOpen, setChatOpen] = useState(false);
    const [chatInput, setChatInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const [messages, setMessages] = useState<Array<{ role: 'user' | 'ai'; text: string }>>([
        {
            role: 'ai',
            text: 'FinCore Neural Copilot active. I am monitoring your SQL multi-currency ledger in real-time. Ask me about your portfolio distribution or automated sweeps.',
        },
    ]);

    const showToast = (msg: string) => {
        setToast(msg);
        setTimeout(() => setToast(null), 3800);
    };

    const validateEmail = (emailStr: string): boolean => {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(emailStr.toLowerCase());
    };

    const apiFetch = async (path: string, options: RequestInit = {}) => {
        const res = await fetch(`${API_BASE}${path}`, {
            ...options,
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...(options.headers || {}),
            },
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
    };

    const syncAllData = async () => {
        if (!token) return;
        setIsRefreshing(true);
        try {
            const [accData, txData, fdData, loanData, riskData] = await Promise.allSettled([
                apiFetch('/accounts/'),
                apiFetch('/transactions/'),
                apiFetch('/fixed-deposits/'),
                apiFetch('/loans/'),
                apiFetch('/risk/alerts'),
            ]);
            if (accData.status === 'fulfilled' && Array.isArray(accData.value)) {
                setAccounts(accData.value);
                if (!fromAcc && accData.value.length > 0) setFromAcc(accData.value[0].account_number);
            }
            if (txData.status === 'fulfilled' && Array.isArray(txData.value)) setTransactions(txData.value);
            if (fdData.status === 'fulfilled' && Array.isArray(fdData.value)) setFds(fdData.value);
            if (loanData.status === 'fulfilled' && Array.isArray(loanData.value)) setLoans(loanData.value);
            if (riskData.status === 'fulfilled' && Array.isArray(riskData.value)) setRiskAlerts(riskData.value);
            setLastSynced(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
            showToast('FinCore Ledger Telemetry Successfully Synchronized');
        } catch (e: any) {
            showToast(e.message || 'Sync warning');
        } finally {
            setTimeout(() => setIsRefreshing(false), 800);
        }
    };

    useEffect(() => { if (token) syncAllData(); }, [token]);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setAuthError('');

        if (!email || !validateEmail(email)) {
            setAuthError('Please enter a valid email address (e.g., name@example.com).');
            return;
        }

        try {
            if (authMode === 'register') {
                await apiFetch('/auth/register', {
                    method: 'POST',
                    body: JSON.stringify({ email, password, full_name: fullName || 'Satya Sai Bareddy' }),
                });
            }
            const formBody = new URLSearchParams({ username: email, password });
            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formBody,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Authentication failed');
            localStorage.setItem('fincore_token', data.access_token);
            setToken(data.access_token);
            showToast('Welcome to FinCore Autonomous Command Center');
        } catch (err: any) {
            setAuthError(err.message);
        }
    };

    const handleCreateVault = async () => {
        try {
            await apiFetch('/accounts/', {
                method: 'POST',
                body: JSON.stringify({ currency: newVaultCurrency, account_type: newVaultType, initial_deposit: parseFloat(initialDeposit) || 0 }),
            });
            showToast(`New ${newVaultCurrency} ${newVaultType} Account Provisioned`);
            await syncAllData();
        } catch (e: any) {
            showToast(e.message);
        }
    };

    const handleDeleteVault = async (accountNumber: string) => {
        if (!window.confirm(`Are you sure you want to close account ${accountNumber}?`)) return;
        try {
            await apiFetch(`/accounts/${encodeURIComponent(accountNumber)}`, { method: 'DELETE' });
            showToast('Account successfully closed & removed');
            await syncAllData();
        } catch (e: any) {
            showToast(e.message);
        }
    };

    const handleTransfer = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/transactions/transfer', {
                method: 'POST',
                body: JSON.stringify({
                    from_account_number: fromAcc,
                    to_account_number: toAcc,
                    amount: parseFloat(txAmount),
                    description: txNote || 'FinCore Instant Transfer',
                }),
            });
            setTxAmount('');
            setToAcc('');
            setTxNote('');
            showToast('Transfer Executed Successfully');
            await syncAllData();
        } catch (e: any) {
            showToast(e.message);
        }
    };

    const handleCreateFD = async () => {
        if (!fromAcc) return showToast('Provision an account first');
        try {
            await apiFetch('/fixed-deposits/', {
                method: 'POST',
                body: JSON.stringify({ account_number: fromAcc, principal_amount: parseFloat(fdAmount), tenure_months: parseInt(fdMonths, 10) }),
            });
            showToast('Term Deposit Successfully Locked at 7.40% APY');
            await syncAllData();
        } catch (e: any) { showToast(e.message); }
    };

    const handleApplyLoan = async () => {
        if (!fromAcc) return showToast('Provision an account first');
        try {
            await apiFetch('/loans/apply', {
                method: 'POST',
                body: JSON.stringify({ account_number: fromAcc, principal_amount: parseFloat(loanAmount), tenure_months: parseInt(loanTenure, 10) }),
            });
            showToast('Instant Credit Disbursed to Account');
            await syncAllData();
        } catch (e: any) { showToast(e.message); }
    };

    const handleSimulateThreat = () => {
        setRiskAlerts(prev => [{
            id: `SIM-${Date.now()}`,
            rule_triggered: 'IMPOSSIBLE_TRAVEL_GEO_VELOCITY',
            description: 'Blocked ₹2,40,000 fraudulent wire attempt from foreign proxy node.',
            status: 'BLOCKED'
        }, ...prev]);
        showToast('Threat Sandbox Intercepted Attack');
    };

    const handleAskCopilot = async (promptOverride?: string) => {
        const query = (promptOverride ?? chatInput).trim();
        if (!query || chatLoading) return;
        setMessages(prev => [...prev, { role: 'user', text: query }]);
        setChatInput('');
        setChatLoading(true);
        try {
            const res = await apiFetch('/copilot/chat', { method: 'POST', body: JSON.stringify({ message: query }) });
            setMessages(prev => [...prev, { role: 'ai', text: res.reply }]);
        } catch (e: any) {
            setMessages(prev => [...prev, { role: 'ai', text: `Ledger query error: ${e.message}` }]);
        } finally {
            setChatLoading(false);
        }
    };

    const totalPortfolioINR = useMemo(
        () => accounts.reduce((acc, a) => acc + Number(a.balance || 0) * (FX_TO_INR[a.currency] || 1), 0),
        [accounts]
    );

    const filteredTransactions = useMemo(() => {
        if (selectedHistoryAccount === 'ALL') return transactions;
        return transactions.filter(t => t.from_account === selectedHistoryAccount || t.to_account === selectedHistoryAccount);
    }, [transactions, selectedHistoryAccount]);

    const analyticsSeries = useMemo(() => {
        const base = totalPortfolioINR || 185000;
        return Array.from({ length: 7 }, (_, i) => {
            const d = new Date();
            d.setDate(d.getDate() - (6 - i));
            return {
                day: d.toLocaleDateString('en-IN', { weekday: 'short' }),
                balance: Math.round(base * (0.92 + i * 0.015)),
                outflow: Math.round(2200 + i * 450),
            };
        });
    }, [totalPortfolioINR]);

    const timeMachineSeries = useMemo(() => {
        const start = totalPortfolioINR || 150000;
        const monthlyRate = 0.092 / 12;
        const savedFromCuts = (simExpenseCutPct / 100) * 22000;
        return Array.from({ length: Math.min(simMonths, 24) + 1 }, (_, m) => {
            const projected = start * Math.pow(1 + monthlyRate, m) + (simMonthlySip + savedFromCuts) * ((Math.pow(1 + monthlyRate, m) - 1) / monthlyRate);
            return { month: `M${m}`, projected: Math.round(projected), baseline: Math.round(start * Math.pow(1.004, m)) };
        });
    }, [totalPortfolioINR, simMonths, simMonthlySip, simExpenseCutPct]);

    const categoryBreakdown = useMemo(() => [
        { name: 'Global FX Transfers', value: 42, color: '#6366f1' },
        { name: 'Automated Yield Vaults', value: 31, color: '#10b981' },
        { name: 'Merchant & Bills', value: 17, color: '#f59e0b' },
        { name: 'Derivatives & Fees', value: 10, color: '#ec4899' },
    ], []);

    if (!token) {
        return (
            <div className="min-h-screen bg-[#030712] text-slate-100 flex items-center justify-center p-4 relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,#312e81_0%,transparent_50%),radial-gradient(circle_at_bottom_left,#065f46_0%,transparent_50%)] opacity-70 animate-pulse" />
                <div className="relative z-10 w-full max-w-md rounded-3xl bg-slate-900/60 backdrop-blur-2xl border border-white/10 p-8 shadow-[0_0_50px_rgba(99,102,241,0.15)]">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="h-12 w-12 rounded-2xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-emerald-400 flex items-center justify-center shadow-xl shadow-indigo-500/20">
                            <Landmark className="h-6 w-6 text-slate-950" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-black tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">FinCore</h1>
                            <p className="text-xs text-indigo-400 font-medium">Autonomous Multi-Currency Core Banking</p>
                        </div>
                    </div>

                    <div className="flex gap-2 p-1.5 rounded-2xl bg-slate-950/80 border border-white/5 mb-6">
                        {(['login', 'register'] as const).map(m => (
                            <button
                                key={m}
                                onClick={() => setAuthMode(m)}
                                className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 cursor-pointer ${authMode === m ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'
                                    }`}
                            >
                                {m === 'login' ? 'Sign In' : 'Open Vaults'}
                            </button>
                        ))}
                    </div>

                    <form onSubmit={handleAuth} className="space-y-4">
                        {authMode === 'register' && (
                            <input
                                type="text"
                                required
                                placeholder="Full Legal Name"
                                value={fullName}
                                onChange={e => setFullName(e.target.value)}
                                className="w-full px-4 py-3 rounded-2xl bg-slate-950/80 border border-white/10 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition text-white"
                            />
                        )}
                        <input
                            type="email"
                            required
                            placeholder="Email Address"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="w-full px-4 py-3 rounded-2xl bg-slate-950/80 border border-white/10 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition text-white"
                        />
                        <input
                            type="password"
                            required
                            placeholder="Password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="w-full px-4 py-3 rounded-2xl bg-slate-950/80 border border-white/10 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition text-white"
                        />
                        {authError && (
                            <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs rounded-xl font-medium">
                                {authError}
                            </div>
                        )}
                        <button
                            type="submit"
                            className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-emerald-500 font-bold text-sm text-white shadow-xl shadow-indigo-600/25 hover:scale-[1.02] active:scale-[0.98] transition duration-300 cursor-pointer"
                        >
                            {authMode === 'login' ? 'Access Command Center' : 'Initialize Autonomous Vaults'}
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    const navItems = [
        { id: 'accounts', label: 'Accounts', icon: Wallet },
        { id: 'transfer', label: 'Transfer', icon: Send },
        { id: 'history', label: 'History', icon: History },
        { id: 'fds', label: 'Deposits', icon: Lock },
        { id: 'loans', label: 'Loans & EMI', icon: CreditCard },
        { id: 'planner', label: 'Planner & AI', icon: Cpu },
        { id: 'security', label: 'Security', icon: ShieldAlert },
    ] as const;

    return (
        <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col lg:flex-row relative selection:bg-indigo-500 selection:text-white">
            {toast && (
                <div className="fixed top-5 right-5 z-50 flex items-center gap-3 px-5 py-4 rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-emerald-500/40 text-emerald-300 text-sm shadow-[0_0_30px_rgba(16,185,129,0.2)] animate-in fade-in slide-in-from-top-4 duration-300">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                    <span className="font-semibold">{toast}</span>
                </div>
            )}

            <aside className={`fixed inset-y-0 left-0 z-40 w-72 bg-slate-950/80 backdrop-blur-2xl border-r border-white/10 p-6 flex flex-col justify-between transition-transform duration-300 lg:static lg:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
                <div>
                    <div className="flex items-center justify-between mb-8">
                        <div className="flex items-center gap-3">
                            <div className="h-11 w-11 rounded-2xl bg-gradient-to-tr from-indigo-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                                <Landmark className="h-5 w-5 text-slate-950" />
                            </div>
                            <div>
                                <span className="font-black tracking-wider text-lg bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">FinCore</span>
                                <span className="block text-[10px] font-bold uppercase tracking-widest text-emerald-400">Autonomous Core</span>
                            </div>
                        </div>
                        <button onClick={() => setMobileMenuOpen(false)} className="lg:hidden text-slate-400 hover:text-white cursor-pointer"><X className="h-5 w-5" /></button>
                    </div>

                    <nav className="space-y-2">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            const active = activeTab === item.id;
                            return (
                                <button
                                    key={item.id}
                                    onClick={() => { setActiveTab(item.id); setMobileMenuOpen(false); }}
                                    className={`w-full flex items-center gap-3.5 px-4 py-3.5 rounded-2xl text-sm font-semibold transition-all duration-300 cursor-pointer ${active
                                        ? 'bg-gradient-to-r from-indigo-600/30 to-indigo-500/10 text-indigo-300 border border-indigo-500/30 shadow-[0_0_20px_rgba(99,102,241,0.15)] translate-x-1'
                                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                        }`}
                                >
                                    <Icon className={`h-4 w-4 ${active ? 'text-indigo-400' : 'text-slate-500'}`} />
                                    <span>{item.label}</span>
                                </button>
                            );
                        })}
                    </nav>
                </div>

                <button
                    onClick={() => { localStorage.removeItem('fincore_token'); setToken(null); }}
                    className="w-full py-3 rounded-2xl border border-white/10 hover:border-rose-500/40 text-xs font-bold text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition duration-300 cursor-pointer"
                >
                    Secure Session Lock & Sign Out
                </button>
            </aside>

            <main className="flex-1 p-4 md:p-8 overflow-y-auto">
                <header className="flex flex-wrap items-center justify-between gap-4 pb-6 mb-8 border-b border-white/10">
                    <div className="flex items-center gap-4">
                        <button onClick={() => setMobileMenuOpen(true)} className="lg:hidden p-2.5 rounded-2xl bg-slate-900 border border-white/10 cursor-pointer"><Menu className="h-5 w-5" /></button>
                        <div>
                            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Consolidated Net Liquidity (INR Eq.)</p>
                            <h2 className="text-3xl md:text-4xl font-black font-mono tracking-tight bg-gradient-to-r from-white via-slate-100 to-indigo-300 bg-clip-text text-transparent">
                                ₹{totalPortfolioINR.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </h2>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <span className="hidden sm:inline-block text-xs font-mono text-slate-500">Synced: {lastSynced}</span>
                        <button
                            onClick={syncAllData}
                            disabled={isRefreshing}
                            className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-slate-900/80 hover:bg-slate-800 border border-white/10 hover:border-indigo-500/40 text-sm font-bold transition duration-300 active:scale-95 cursor-pointer shadow-lg shadow-black/40"
                        >
                            <RefreshCw className={`h-4 w-4 text-emerald-400 transition-transform duration-700 ${isRefreshing ? 'animate-spin' : 'hover:rotate-180'}`} />
                            <span>{isRefreshing ? 'Synchronizing Ledger...' : 'Refresh Live'}</span>
                        </button>
                    </div>
                </header>

                <WorkspaceErrorBoundary>
                    {isRefreshing ? (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
                            {[1, 2, 3].map(n => (
                                <div key={n} className="h-44 rounded-3xl bg-slate-900/60 border border-white/5 flex flex-col justify-between p-6">
                                    <div className="h-6 w-24 bg-slate-800 rounded-full animate-pulse" />
                                    <div className="h-8 w-36 bg-slate-800 rounded-xl animate-pulse" />
                                    <div className="h-4 w-28 bg-slate-800 rounded animate-pulse" />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <>
                            {activeTab === 'accounts' && (
                                <div className="space-y-6 animate-in fade-in duration-500">
                                    <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl">
                                        <div className="flex flex-wrap items-center gap-3">
                                            <select value={newVaultCurrency} onChange={e => setNewVaultCurrency(e.target.value)} className="px-4 py-2.5 rounded-2xl bg-slate-950 border border-white/10 text-sm font-semibold outline-none cursor-pointer">
                                                {['INR', 'USD', 'EUR', 'GBP'].map(c => <option key={c} value={c}>{c}</option>)}
                                            </select>
                                            <select value={newVaultType} onChange={e => setNewVaultType(e.target.value)} className="px-4 py-2.5 rounded-2xl bg-slate-950 border border-white/10 text-sm font-semibold outline-none cursor-pointer">
                                                <option value="SAVINGS">SAVINGS (4.25% APY)</option>
                                                <option value="CURRENT">CURRENT (0.50% APY)</option>
                                                <option value="TREASURY">TREASURY (6.80% APY)</option>
                                            </select>
                                            <input type="number" placeholder="Initial Deposit" value={initialDeposit} onChange={e => setInitialDeposit(e.target.value)} className="w-36 px-4 py-2.5 rounded-2xl bg-slate-950 border border-white/10 text-sm font-semibold outline-none text-white" />
                                        </div>
                                        <button onClick={handleCreateVault} className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-emerald-500 hover:scale-105 font-bold text-sm shadow-lg shadow-indigo-600/30 transition duration-300 cursor-pointer">
                                            <Plus className="h-4 w-4" /> Provision Account
                                        </button>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                                        {accounts.map(acc => (
                                            <div
                                                key={acc.account_number}
                                                onClick={() => { setSelectedHistoryAccount(acc.account_number); setActiveTab('history'); }}
                                                className="group relative p-6 rounded-3xl bg-gradient-to-br from-slate-900/80 via-slate-950/90 to-slate-900/80 backdrop-blur-2xl border border-white/10 hover:border-indigo-500/50 shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
                                                title="Click to view transaction history for this account"
                                            >
                                                <div className="flex items-center justify-between mb-4">
                                                    <span className="px-3.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                                                        {acc.currency} • {acc.account_type}
                                                    </span>
                                                    <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                                                        <Globe className="h-4 w-4 text-slate-500 group-hover:text-indigo-400 transition" />
                                                        <button onClick={() => handleDeleteVault(acc.account_number)} title="Close Account" className="p-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition cursor-pointer">
                                                            <Trash2 className="h-4 w-4" />
                                                        </button>
                                                    </div>
                                                </div>
                                                <p className="text-3xl font-black font-mono mb-2 tracking-tight">
                                                    {CURRENCY_SYMBOL[acc.currency] || ''}{Number(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                </p>
                                                <p className="text-xs font-mono text-slate-400 flex items-center justify-between">
                                                    <span>A/C: {acc.account_number}</span>
                                                    <span className="text-indigo-400 opacity-0 group-hover:opacity-100 transition text-[11px] font-bold">View History →</span>
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {activeTab === 'transfer' && (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-500">
                                    <form onSubmit={handleTransfer} className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl space-y-4">
                                        <h3 className="text-lg font-bold flex items-center gap-2"><Send className="h-5 w-5 text-indigo-400" /> Account Transfer</h3>
                                        <p className="text-xs text-slate-400">Transfer funds securely between valid internal account numbers.</p>
                                        <label className="text-xs font-semibold text-slate-400 block">From Account</label>
                                        <select value={fromAcc} onChange={e => setFromAcc(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm font-semibold outline-none cursor-pointer">
                                            {accounts.map(a => <option key={a.account_number} value={a.account_number}>{a.account_number} ({a.currency} {a.balance})</option>)}
                                        </select>
                                        <label className="text-xs font-semibold text-slate-400 block">To Account Number</label>
                                        <input type="text" required placeholder="e.g. ACC-1-INR" value={toAcc} onChange={e => setToAcc(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none focus:border-indigo-500 transition font-mono text-white" />
                                        <input type="number" required min="1" step="0.01" placeholder="Amount" value={txAmount} onChange={e => setTxAmount(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none focus:border-indigo-500 transition text-white" />
                                        <input type="text" placeholder="Narration / Reference Note" value={txNote} onChange={e => setTxNote(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none focus:border-indigo-500 transition text-white" />
                                        <button type="submit" className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-emerald-500 hover:scale-[1.01] active:scale-[0.99] font-bold text-sm shadow-xl shadow-indigo-600/25 transition cursor-pointer">
                                            Send Money Instantly
                                        </button>
                                    </form>

                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-emerald-500/30 shadow-2xl space-y-4">
                                        <div className="flex items-center gap-2.5">
                                            <Zap className="h-5 w-5 text-emerald-400 animate-pulse" />
                                            <h3 className="text-lg font-bold">Auto-Sweep Rule Engine</h3>
                                        </div>
                                        <p className="text-xs text-slate-400">Configure conditional logic to automatically divert incoming deposits into reserve savings.</p>
                                        <div className="flex gap-3">
                                            <input type="number" value={ruleTrigger} onChange={e => setRuleTrigger(e.target.value)} placeholder="Min Credit ₹" className="w-1/2 px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none text-white" />
                                            <input type="number" value={rulePct} onChange={e => setRulePct(e.target.value)} placeholder="Sweep %" className="w-1/2 px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none text-white" />
                                        </div>
                                        <button onClick={() => { setRules(prev => [...prev, { id: `r-${Date.now()}`, trigger: Number(ruleTrigger), pct: Number(rulePct), target: 'Auto-Wealth Vault', active: true }]); showToast('Auto-Sweep Rule Deployed Successfully'); }} className="w-full py-3 rounded-2xl bg-emerald-600/20 border border-emerald-500/40 hover:bg-emerald-600/30 text-emerald-300 font-bold text-sm transition cursor-pointer shadow-lg shadow-emerald-500/10">
                                            + Deploy Auto-Sweep Rule
                                        </button>
                                        <div className="space-y-2 pt-2">
                                            {rules.map(r => (
                                                <div key={r.id} className="p-3.5 rounded-2xl bg-slate-950/80 border border-white/5 flex items-center justify-between text-xs font-mono">
                                                    <span>IF credit ≥ <b>₹{r.trigger.toLocaleString()}</b> → Auto-sweep <b>{r.pct}%</b></span>
                                                    <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-bold">ACTIVE</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeTab === 'history' && (
                                <div className="space-y-6 animate-in fade-in duration-500">
                                    <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl">
                                        <div className="flex items-center gap-3">
                                            <History className="h-5 w-5 text-indigo-400" />
                                            <h3 className="text-base font-bold">Transaction History & Ledger Stream</h3>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className="text-xs text-slate-400">Filter Account:</span>
                                            <select
                                                value={selectedHistoryAccount}
                                                onChange={e => setSelectedHistoryAccount(e.target.value)}
                                                className="px-4 py-2.5 rounded-2xl bg-slate-950 border border-white/10 text-sm font-semibold outline-none cursor-pointer"
                                            >
                                                <option value="ALL">All Accounts (Consolidated)</option>
                                                {accounts.map(a => (
                                                    <option key={a.account_number} value={a.account_number}>{a.account_number} ({a.currency})</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    <div className="p-6 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl">
                                        <div className="space-y-3">
                                            {filteredTransactions.length === 0 ? (
                                                <p className="text-sm text-slate-400 text-center py-8">No transaction records found for this account selection.</p>
                                            ) : (
                                                filteredTransactions.map((t, idx) => (
                                                    <div key={t.id || idx} className="flex items-center justify-between p-4 rounded-2xl bg-slate-950/60 border border-white/5 hover:border-white/10 transition">
                                                        <div className="flex items-center gap-4">
                                                            <div className="h-10 w-10 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
                                                                <ArrowUpRight className="h-5 w-5 text-indigo-400" />
                                                            </div>
                                                            <div>
                                                                <p className="text-sm font-bold">{t.description || 'Account Settlement'}</p>
                                                                <p className="text-xs text-slate-400 font-mono">From: {t.from_account} → To: {t.to_account} | Ref: {t.reference_id}</p>
                                                            </div>
                                                        </div>
                                                        <span className="font-mono font-bold text-emerald-400 text-base">₹{Number(t.amount).toLocaleString('en-IN')}</span>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeTab === 'fds' && (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-500">
                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl space-y-4">
                                        <h3 className="text-lg font-bold flex items-center gap-2"><Lock className="h-5 w-5 text-indigo-400" /> Fixed Deposits (7.40% APY)</h3>
                                        <p className="text-xs text-slate-400">Minimum principal: ₹5,000. Locked directly from your selected account balance.</p>
                                        <input type="number" min="5000" value={fdAmount} onChange={e => setFdAmount(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none text-white" />
                                        <select value={fdMonths} onChange={e => setFdMonths(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none cursor-pointer">
                                            <option value="6">6 Months Term (7.10% APY)</option>
                                            <option value="12">12 Months Term (7.40% APY)</option>
                                            <option value="24">24 Months Term (7.80% APY)</option>
                                        </select>
                                        <button onClick={handleCreateFD} className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 font-bold text-sm shadow-xl shadow-indigo-600/25 hover:scale-[1.01] transition cursor-pointer">
                                            Lock Fixed Deposit
                                        </button>
                                    </div>
                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl space-y-3">
                                        <h3 className="text-lg font-bold">Active Fixed Deposits ({fds.length})</h3>
                                        {fds.length === 0 ? (
                                            <p className="text-sm text-slate-400">No active term deposits locked.</p>
                                        ) : (
                                            fds.map((fd, i) => (
                                                <div key={fd.id || i} className="p-4 rounded-2xl bg-slate-950/80 border border-white/5 flex justify-between items-center text-sm">
                                                    <span className="font-semibold">Principal: ₹{Number(fd.principal_amount).toLocaleString('en-IN')}</span>
                                                    <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 font-mono text-xs font-bold">{fd.tenure_months}M @ 7.4% APY</span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}

                            {activeTab === 'loans' && (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-500">
                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl space-y-4">
                                        <h3 className="text-lg font-bold flex items-center gap-2"><CreditCard className="h-5 w-5 text-indigo-400" /> Loans & EMI Facility</h3>
                                        <p className="text-xs text-slate-400">Limits: ₹10,000 up to ₹25,00,000 disbursed instantly into your account.</p>
                                        <input type="number" min="10000" max="2500000" value={loanAmount} onChange={e => setLoanAmount(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none text-white" />
                                        <select value={loanTenure} onChange={e => setLoanTenure(e.target.value)} className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/10 text-sm outline-none cursor-pointer">
                                            <option value="12">12 Months EMI</option>
                                            <option value="24">24 Months EMI</option>
                                            <option value="36">36 Months EMI</option>
                                        </select>
                                        <button onClick={handleApplyLoan} className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-emerald-500 font-bold text-sm shadow-xl shadow-indigo-600/25 hover:scale-[1.01] transition cursor-pointer">
                                            Disburse Loan
                                        </button>
                                    </div>
                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl space-y-3">
                                        <h3 className="text-lg font-bold">Active Loans ({loans.length})</h3>
                                        {loans.length === 0 ? (
                                            <p className="text-sm text-slate-400">No active loans or credit facilities.</p>
                                        ) : (
                                            loans.map((l, i) => (
                                                <div key={l.id || i} className="p-4 rounded-2xl bg-slate-950/80 border border-white/5 flex justify-between items-center text-sm">
                                                    <span className="font-semibold">Principal: ₹{Number(l.principal_amount).toLocaleString('en-IN')}</span>
                                                    <span className="px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 font-mono text-xs font-bold">EMI: ₹{Number(l.monthly_emi || 0).toLocaleString('en-IN')}</span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}

                            {activeTab === 'planner' && (
                                <div className="space-y-6 animate-in fade-in duration-500">
                                    <div className="p-7 rounded-3xl bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-slate-950/80 backdrop-blur-2xl border border-indigo-500/30 shadow-2xl">
                                        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                                            <div>
                                                <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">FinCore Exclusive Engine</span>
                                                <h3 className="text-xl font-black">Interactive Wealth Time-Machine</h3>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-xs text-slate-400">Projected Net Worth (+{simMonths} Months)</p>
                                                <p className="text-3xl font-black font-mono text-emerald-400">
                                                    ₹{timeMachineSeries[timeMachineSeries.length - 1]?.projected.toLocaleString('en-IN')}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
                                            <div className="p-5 rounded-2xl bg-slate-950/80 border border-white/5">
                                                <label className="text-xs font-semibold text-slate-400 block mb-2">Simulation Horizon: {simMonths} Months</label>
                                                <input type="range" min="3" max="24" value={simMonths} onChange={e => setSimMonths(Number(e.target.value))} className="w-full accent-indigo-500 cursor-pointer" />
                                            </div>
                                            <div className="p-5 rounded-2xl bg-slate-950/80 border border-white/5">
                                                <label className="text-xs font-semibold text-slate-400 block mb-2">Monthly Auto-SIP: ₹{simMonthlySip.toLocaleString()}</label>
                                                <input type="range" min="0" max="100000" step="5000" value={simMonthlySip} onChange={e => setSimMonthlySip(Number(e.target.value))} className="w-full accent-emerald-500 cursor-pointer" />
                                            </div>
                                            <div className="p-5 rounded-2xl bg-slate-950/80 border border-white/5">
                                                <label className="text-xs font-semibold text-slate-400 block mb-2">Trim Lifestyle Spend: {simExpenseCutPct}%</label>
                                                <input type="range" min="0" max="40" step="5" value={simExpenseCutPct} onChange={e => setSimExpenseCutPct(Number(e.target.value))} className="w-full accent-amber-500 cursor-pointer" />
                                            </div>
                                        </div>

                                        <div className="w-full h-[300px]">
                                            <ResponsiveContainer width="100%" height={300}>
                                                <AreaChart data={timeMachineSeries}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
                                                    <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} />
                                                    <YAxis stroke="#94a3b8" fontSize={12} />
                                                    <Tooltip contentStyle={{ backgroundColor: '#030712', borderColor: '#334155', borderRadius: '1rem', color: '#fff' }} />
                                                    <Area type="monotone" dataKey="projected" stroke="#10b981" fill="#10b981" fillOpacity={0.2} strokeWidth={2} />
                                                    <Area type="monotone" dataKey="baseline" stroke="#6366f1" fill="#6366f1" fillOpacity={0.1} strokeWidth={2} />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                        <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl">
                                            <h4 className="text-base font-bold mb-4">7-Day Cash-Flow Velocity</h4>
                                            <div className="w-full h-[260px]">
                                                <ResponsiveContainer width="100%" height={260}>
                                                    <BarChart data={analyticsSeries}>
                                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
                                                        <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} />
                                                        <YAxis stroke="#94a3b8" fontSize={12} />
                                                        <Tooltip contentStyle={{ backgroundColor: '#030712', borderColor: '#334155', borderRadius: '1rem', color: '#fff' }} itemStyle={{ color: '#fff' }} />
                                                        <Bar dataKey="outflow" fill="#6366f1" radius={[8, 8, 0, 0]} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>

                                        <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl">
                                            <h4 className="text-base font-bold mb-4">AI Outflow Attribution</h4>
                                            <div className="w-full h-[260px]">
                                                <ResponsiveContainer width="100%" height={260}>
                                                    <PieChart>
                                                        <Pie data={categoryBreakdown} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={4}>
                                                            {categoryBreakdown.map((entry, idx) => <Cell key={idx} fill={entry.color} />)}
                                                        </Pie>
                                                        <Tooltip contentStyle={{ backgroundColor: '#030712', borderColor: '#334155', borderRadius: '1rem', color: '#fff' }} itemStyle={{ color: '#fff' }} />
                                                    </PieChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeTab === 'security' && (
                                <div className="space-y-6 animate-in fade-in duration-500">
                                    <div className="p-7 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-rose-500/30 shadow-2xl flex flex-wrap items-center justify-between gap-4">
                                        <div>
                                            <h3 className="text-lg font-bold">Threat Sandbox & Security</h3>
                                            <p className="text-xs text-slate-400">Test autonomous zero-trust fraud blocking mechanisms.</p>
                                        </div>
                                        <button onClick={handleSimulateThreat} className="px-5 py-3 rounded-2xl bg-gradient-to-r from-rose-600 to-rose-500 hover:scale-105 font-bold text-sm shadow-xl shadow-rose-600/30 transition cursor-pointer">
                                            Simulate Attack Vector
                                        </button>
                                    </div>

                                    <div className="space-y-3">
                                        {riskAlerts.length === 0 ? (
                                            <div className="p-6 rounded-2xl bg-slate-900/40 backdrop-blur-xl border border-white/10 text-sm text-emerald-400 font-medium">
                                                Zero perimeter anomalies. Neural threat firewall fully nominal.
                                            </div>
                                        ) : (
                                            riskAlerts.map((alert, i) => (
                                                <div key={alert.id || i} className="p-5 rounded-2xl bg-rose-950/30 backdrop-blur-xl border border-rose-500/40 flex items-center justify-between">
                                                    <div>
                                                        <span className="text-xs font-bold font-mono text-rose-400">{alert.rule_triggered}</span>
                                                        <p className="text-sm font-medium text-slate-200">{alert.description}</p>
                                                    </div>
                                                    <span className="px-3.5 py-1.5 rounded-full text-xs font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">BLOCKED</span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </WorkspaceErrorBoundary>
            </main>

            <div className="fixed bottom-6 right-6 z-50">
                {chatOpen ? (
                    <div className="w-[380px] sm:w-[420px] h-[520px] rounded-3xl bg-slate-950/90 backdrop-blur-2xl border border-indigo-500/40 shadow-[0_0_50px_rgba(99,102,241,0.25)] flex flex-col overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-4.5 bg-gradient-to-r from-indigo-600/30 via-purple-600/20 to-emerald-600/20 border-b border-white/10 flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="h-8 w-8 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center">
                                    <Bot className="h-4 w-4 text-emerald-400 animate-pulse" />
                                </div>
                                <div>
                                    <h4 className="text-sm font-bold">FinCore Neural Copilot</h4>
                                    <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">● Live SQL Ledger Grounded</span>
                                </div>
                            </div>
                            <button onClick={() => setChatOpen(false)} className="text-slate-400 hover:text-white cursor-pointer"><X className="h-4 w-4" /></button>
                        </div>

                        <div className="flex-1 p-4 overflow-y-auto space-y-3.5 text-sm">
                            {messages.map((m, idx) => (
                                <div key={idx} className={`p-3.5 rounded-2xl whitespace-pre-line leading-relaxed ${m.role === 'user' ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white ml-8 shadow-lg shadow-indigo-600/20 text-xs font-medium' : 'bg-slate-900/80 backdrop-blur-xl border border-white/10 text-slate-200 mr-8 text-xs'}`}>
                                    {m.text}
                                </div>
                            ))}
                            {chatLoading && <p className="text-xs font-mono text-indigo-400 animate-pulse pl-2">Querying multi-currency SQL ledger...</p>}
                        </div>

                        <div className="px-3 pb-2 flex gap-2 overflow-x-auto no-scrollbar">
                            {['Summarize all vault balances', 'Average monthly expenditure?'].map(chip => (
                                <button key={chip} onClick={() => handleAskCopilot(chip)} className="shrink-0 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-white/10 text-[11px] font-medium text-slate-300 transition cursor-pointer">
                                    {chip}
                                </button>
                            ))}
                        </div>

                        <form onSubmit={e => { e.preventDefault(); handleAskCopilot(); }} className="p-3 border-t border-white/10 flex gap-2">
                            <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Ask ledger balances, spending velocity..." className="flex-1 px-4 py-2.5 rounded-2xl bg-slate-900/90 border border-white/10 text-xs outline-none focus:border-indigo-500 transition text-white" />
                            <button type="submit" className="p-2.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-emerald-500 text-white shadow-lg cursor-pointer hover:scale-105 transition"><Send className="h-4 w-4" /></button>
                        </form>
                    </div>
                ) : (
                    <button onClick={() => setChatOpen(true)} className="flex items-center gap-2.5 px-6 py-4 rounded-full bg-gradient-to-r from-indigo-600 via-purple-600 to-emerald-500 text-white font-bold text-sm shadow-[0_0_30px_rgba(99,102,241,0.4)] hover:scale-105 transition duration-300 cursor-pointer">
                        <Sparkles className="h-4 w-4 animate-spin" />
                        <span>Open Neural Copilot</span>
                    </button>
                )}
            </div>
        </div>
    );
}