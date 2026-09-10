"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Shield, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, enroll2FA, verify2FA, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [twoFactorRequired, setTwoFactorRequired] = useState(false);
  const [mfaSetupRequired, setMfaSetupRequired] = useState(false);
  const [mfaSecret, setMfaSecret] = useState("");
  const [mfaUri, setMfaUri] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!twoFactorRequired || !mfaSetupRequired || mfaSecret) return;
    let active = true;
    void enroll2FA().then((result) => {
      if (!active) return;
      if (result.success) {
        setMfaSecret(result.secret || "");
        setMfaUri(result.otpauth_uri || "");
      } else {
        setError(result.message || "تعذر إعداد المصادقة الثنائية");
      }
    });
    return () => { active = false; };
  }, [twoFactorRequired, mfaSetupRequired, mfaSecret, enroll2FA]);

  if (isAuthenticated) { router.push("/"); return null; }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) { router.push("/"); return; }
    if (result.two_factor_required) {
      setMfaSetupRequired(!!result.mfa_setup_required);
      setTwoFactorRequired(true);
      return;
    }
    setError(result.message || "خطأ في تسجيل الدخول");
  };

  const handle2FA = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await verify2FA(twoFactorCode);
    setLoading(false);
    if (result.success) { router.push("/"); return; }
    setError(result.message || "رمز 2FA غير صحيح");
  };

  const resetMfa = () => {
    setTwoFactorRequired(false);
    setMfaSetupRequired(false);
    setMfaSecret("");
    setMfaUri("");
    setTwoFactorCode("");
    setError("");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">ERP Control Center</h1>
          <p className="text-slate-400 mt-1">Master Admin Portal</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {!twoFactorRequired ? (
            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  placeholder="admin@example.com" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
                <div className="relative">
                  <input type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                    placeholder="••••••••" required />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition" aria-label={showPassword ? "Hide password" : "Show password"}>
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              {error && <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>}
              <button type="submit" disabled={loading} className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-xl transition flex items-center justify-center gap-2">
                {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : "Login"}
              </button>
            </form>
          ) : (
            <form onSubmit={handle2FA} className="space-y-5">
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-amber-500/20 rounded-xl mb-3">
                  <Shield className="w-6 h-6 text-amber-400" />
                </div>
                <p className="text-slate-300">
                  {mfaSetupRequired ? "إعداد المصادقة الثنائية مطلوب قبل دخول لوحة التحكم" : "أدخل رمز المصادقة الثنائية"}
                </p>
              </div>
              {mfaSetupRequired && (
                <div className="space-y-3 rounded-xl bg-slate-900/50 border border-slate-700 p-4 text-sm text-slate-300">
                  <p>أضف الحساب إلى تطبيق المصادقة باستخدام QR أو URI:</p>
                  {mfaUri && <code className="block break-all text-xs text-slate-400">{mfaUri}</code>}
                  {mfaSecret && <p><span className="text-slate-400">المفتاح:</span> <code className="text-white">{mfaSecret}</code></p>}
                  <p className="text-xs text-slate-400">لا تشارك هذا المفتاح؛ سيظهر فقط أثناء الإعداد الحالي.</p>
                </div>
              )}
              <div>
                <input type="text" inputMode="numeric" pattern="[0-9]{6}" value={twoFactorCode} onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-center text-2xl tracking-[0.5em] font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                  placeholder="000000" maxLength={6} autoComplete="one-time-code" required autoFocus />
              </div>
              {error && <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>}
              <button type="submit" disabled={loading || twoFactorCode.length !== 6} className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-xl transition flex items-center justify-center gap-2">
                {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : "تحقق"}
              </button>
              <button type="button" onClick={resetMfa} className="w-full py-2 text-slate-400 hover:text-white text-sm transition">العودة لتسجيل الدخول</button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
