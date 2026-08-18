import React, { useState } from "react";
import { BrandLogo } from "../common/BrandLogo";
import { ThemeToggle } from "../common/ThemeToggle";
import { OTPVerification } from "./OTPVerification";
import { useTheme } from "../../theme/ThemeContext";
import { resilientFetch } from "../../services/api";
import { Lock, User, Eye, EyeOff, ShieldCheck } from "lucide-react";

interface AuthScreenProps {
  onLoginSuccess: (token: string, name: string) => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ onLoginSuccess }) => {
  const { theme } = useTheme();
  const [step, setStep] = useState<"login" | "otp">("login");
  
  // Login form state
  const [username, setUsername] = useState<string>("yogeshpadwal16");
  const [password, setPassword] = useState<string>("");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // OTP state from server
  const [sessionId, setSessionId] = useState<string>("");
  const [maskedMobile, setMaskedMobile] = useState<string>("");
  const [devOtpCode, setDevOtpCode] = useState<string | undefined>(undefined);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);

    try {
      const res = await resilientFetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (res.ok && data.status === "otp_required") {
        setSessionId(data.session_id);
        setMaskedMobile(data.masked_mobile);
        setDevOtpCode(data.otp_code);
        setStep("otp");
      } else {
        setErrorMsg(data.message || "Invalid username or password.");
      }
    } catch (err) {
      setErrorMsg("Unable to connect to authentication service.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center relative p-4 bg-slate-950 text-slate-100 font-sans overflow-hidden dark:bg-slate-950 light:bg-slate-50 light:text-slate-900 transition-colors">
      {/* Background Glow Accents */}
      <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-orange-500/10 blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-amber-500/10 blur-3xl pointer-events-none" />

      {/* Top Header Controls */}
      <div className="absolute top-6 right-6 flex items-center gap-3">
        <ThemeToggle size="sm" />
      </div>

      {/* Brand Header */}
      <div className="mb-8 flex flex-col items-center text-center">
        <BrandLogo variant="full" size="lg" className="mb-2" />
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-500 text-[11px] font-bold tracking-wider uppercase">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Single-Owner Command Console</span>
        </div>
      </div>

      {/* Step 1: User ID + Password Form */}
      {step === "login" && (
        <form
          onSubmit={handleLoginSubmit}
          className="w-full max-w-md p-6 sm:p-8 rounded-2xl bg-slate-900/90 dark:bg-slate-900/90 light:bg-white border border-slate-800 dark:border-slate-800 light:border-slate-200 shadow-2xl backdrop-blur-xl transition-all"
        >
          <div className="mb-6">
            <h2 className="text-xl font-bold text-white dark:text-white light:text-slate-900">
              Owner Sign In
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-400 light:text-slate-500 mt-1">
              Enter your authorized owner credentials to request OTP verification.
            </p>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-medium">
              {errorMsg}
            </div>
          )}

          {/* User ID Field */}
          <div className="mb-4">
            <label className="block text-xs font-semibold text-slate-300 dark:text-slate-300 light:text-slate-700 mb-1.5">
              Authorized User ID
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter User ID"
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-800 dark:border-slate-800 light:border-slate-200 bg-slate-950/60 dark:bg-slate-950/60 light:bg-slate-50 text-white dark:text-white light:text-slate-900 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-all font-mono"
              />
            </div>
          </div>

          {/* Password Field */}
          <div className="mb-6">
            <label className="block text-xs font-semibold text-slate-300 dark:text-slate-300 light:text-slate-700 mb-1.5">
              Account Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-slate-800 dark:border-slate-800 light:border-slate-200 bg-slate-950/60 dark:bg-slate-950/60 light:bg-slate-50 text-white dark:text-white light:text-slate-900 text-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-all font-mono"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 shadow-lg shadow-orange-500/20 active:scale-[0.98] transition-all disabled:opacity-50"
          >
            {loading ? "Validating Owner Credentials..." : "Continue to OTP Security Check"}
          </button>
        </form>
      )}

      {/* Step 2: Mobile OTP Verification */}
      {step === "otp" && (
        <OTPVerification
          sessionId={sessionId}
          maskedMobile={maskedMobile}
          devOtpCode={devOtpCode}
          onVerifySuccess={onLoginSuccess}
          onBackToLogin={() => setStep("login")}
        />
      )}

      {/* Footer System Disclaimer */}
      <div className="mt-8 text-center text-[11px] text-slate-500 dark:text-slate-500 light:text-slate-400">
        Project Loot Raiders • Authoritative Single-Owner Operating System
      </div>
    </div>
  );
};
