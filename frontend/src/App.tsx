import React, { useState } from 'react';

export default function App() {
    const [fullName, setFullName] = useState<string>('');
    const [email, setEmail] = useState<string>('');
    const [password, setPassword] = useState<string>('');

    const [errorMsg, setErrorMsg] = useState<string>('');
    const [successMsg, setSuccessMsg] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);

    // Robust email validation regex
    const validateEmail = (emailStr: string): boolean => {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(emailStr.toLowerCase());
    };

    const handleLoginOrVault = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setErrorMsg('');
        setSuccessMsg('');

        // 1. Validate Email format
        if (!email || !validateEmail(email)) {
            setErrorMsg('Please enter a valid email address (e.g., name@example.com).');
            return;
        }

        if (!password) {
            setErrorMsg('Please enter your password.');
            return;
        }

        setLoading(true);

        const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://fincore-backend-4fi9.onrender.com';

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    full_name: fullName || 'User',
                    email: email,
                    password: password,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to authenticate with autonomous vaults.');
            }

            setSuccessMsg('Successfully connected to FinCore Vaults!');
        } catch (err: any) {
            console.error('Fetch error:', err);
            setErrorMsg(err.message || 'Failed to fetch. Please check your network or backend connection.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
                <h2 className="text-2xl font-bold text-white mb-2">FinCore</h2>
                <p className="text-sm text-slate-400 mb-6">Autonomous Multi-Currency Core Banking</p>

                {errorMsg && (
                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg flex items-center justify-between">
                        <span>{errorMsg}</span>
                        <button onClick={() => setErrorMsg('')} className="text-red-400 font-bold ml-2">×</button>
                    </div>
                )}

                {successMsg && (
                    <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm rounded-lg">
                        {successMsg}
                    </div>
                )}

                <form onSubmit={handleLoginOrVault} className="space-y-4">
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Full Name</label>
                        <input
                            type="text"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder="Enter your name"
                            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@example.com"
                            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                        {loading ? 'Connecting...' : 'Initialize Autonomous Vaults'}
                    </button>
                </form>
            </div>
        </div>
    );
}