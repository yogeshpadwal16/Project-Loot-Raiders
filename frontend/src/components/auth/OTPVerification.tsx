import React, { useState, useRef, useEffect } from "react";
import { Shield, ArrowLeft, RefreshCw, CheckCircle2, AlertCircle, Lock } from "lucide-react";

interface OTPVerificationProps {
  sessionId: string;
  maskedMobile: string;
  onVerifySuccess: (token: string, name: string) => void;
  onBackToLogin: () => void;
}

export const OTPVerification: React.FC<OTPVerificationProps> = ({
  sessionId,
  maskedMobile,
  onVerifySuccess,
  onBackToLogin,
}) => {
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [countdown, setCountdown] = useState<number>(60);
  const [loading, setLoading] = useState<boolean>(false);
  const [resending, setResending] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Auto-focus first digit input box on mount
  useEffect(() => {
    if (inputRefs.current[0]) {
      inputRefs.current[0].focus();
    }
  }, []);

  // 60-second countdown timer
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  const handleDigitChange = (index: number, val: string) => {
    setErrorMsg(null);

    // Filter non-numeric characters
    const numeric = val.replace(/\D/g, "");
    if (!numeric) {
      const updated = [...digits];
      updated[index] = "";
      setDigits(updated);
      return;
    }

    // Single digit input
    const singleChar = numeric.slice(-1);
    const updated = [...digits];
    updated[index] = singleChar;
    setDigits(updated);

    // Auto-advance focus
    if (index < 5 && singleChar) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit if all 6 digits entered
    if (updated.every((d) => d.length === 1)) {
      submitOTP(updated.join(""));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (!digits[index] && index > 0) {
        // Move focus backward if current box is empty
        inputRefs.current[index - 1]?.focus();
      }
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;

    const newDigits = Array(6).fill("");
    for (let i = 0; i < pasted.length; i++) {
      newDigits[i] = pasted[i];
    }
    setDigits(newDigits);

    if (pasted.length === 6) {
      submitOTP(pasted);
    } else {
      inputRefs.current[Math.min(pasted.length, 5)]?.focus();
    }
  };

  const submitOTP = async (code: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, otp: code }),
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setSuccessMsg("Owner Verification Successful!");
        setTimeout(() => {
          onVerifySuccess(data.token, data.name || "Owner");
        }, 600);
      } else {
        setErrorMsg(data.message || "Invalid verification code.");
      }
    } catch (err: any) {
      setErrorMsg("Network error. Could not connect to verification server.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || resending) return;
    setResending(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/resend-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      if (res.ok && data.status === "sent") {
        setCountdown(60);
        setDigits(Array(6).fill(""));
        setSuccessMsg(`Fresh verification code sent to ${maskedMobile}`);
        setTimeout(() => setSuccessMsg(null), 3000);
        inputRefs.current[0]?.focus();
      } else {
        setErrorMsg(data.message || "Failed to resend code.");
      }
    } catch (err) {
      setErrorMsg("Failed to connect to resend service.");
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="w-full max-w-md p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl backdrop-blur-xl transition-all">
      {/* Top Header */}
      <button
        onClick={onBackToLogin}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Login
      </button>

      <div className="text-center mb-6">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-orange-500 mb-4 shadow-lg shadow-orange-500/10">
          <Shield className="w-7 h-7" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
          Owner Security Check
        </h2>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
          Verification code sent to registered owner line:
        </p>
        <div className="inline-flex items-center gap-2 mt-1.5 px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs font-mono font-bold text-orange-600 dark:text-orange-400">
          <Lock className="w-3 h-3" />
          <span>{maskedMobile}</span>
        </div>
      </div>

      {/* Success Notification Banner */}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-medium flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Error Notification Banner */}
      {errorMsg && (
        <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center gap-2 animate-shake">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 6-Digit Individual Box Input Grid (Matching Reference Layout) */}
      <div className="flex justify-between gap-2 sm:gap-3 mb-6" onPaste={handlePaste}>
        {digits.map((digit, index) => (
          <input
            key={index}
            ref={(el) => (inputRefs.current[index] = el)}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleDigitChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            disabled={loading}
            className={`w-11 h-13 sm:w-12 sm:h-14 text-center text-xl font-bold font-mono rounded-xl border transition-all duration-200 outline-none ${
              digit
                ? "border-orange-500 bg-orange-500/5 text-orange-600 dark:text-orange-400 shadow-md shadow-orange-500/10"
                : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-slate-900 dark:text-white focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
            } ${errorMsg ? "border-rose-500 text-rose-500" : ""}`}
          />
        ))}
      </div>

      {/* Primary Action Button */}
      <button
        onClick={() => submitOTP(digits.join(""))}
        disabled={loading || digits.some((d) => !d)}
        className="w-full py-3.5 px-4 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 shadow-lg shadow-orange-500/25 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none transition-all flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Verifying Owner Token...</span>
          </>
        ) : (
          <span>Authenticate Session</span>
        )}
      </button>

      {/* Countdown & Resend Section */}
      <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-sans">
        <span>Didn't receive code?</span>
        {countdown > 0 ? (
          <span className="font-mono font-medium text-orange-600 dark:text-orange-400">
            Resend in {countdown}s
          </span>
        ) : (
          <button
            onClick={handleResend}
            disabled={resending}
            className="font-bold text-orange-500 hover:text-orange-600 dark:hover:text-orange-400 underline underline-offset-2 flex items-center gap-1 disabled:opacity-50"
          >
            {resending && <RefreshCw className="w-3 h-3 animate-spin" />}
            <span>Resend Code</span>
          </button>
        )}
      </div>
    </div>
  );
};
