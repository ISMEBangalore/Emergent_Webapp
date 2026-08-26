import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { GraduationCap, LockKey } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const from = loc.state?.from?.pathname || "/";

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api.login(username.trim(), password);
      login(data.access_token, data.username);
      nav(from, { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || "Invalid username or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center p-4 relative overflow-hidden">
      <img
        src="/isme-logo.png"
        alt=""
        aria-hidden="true"
        className="hidden sm:block pointer-events-none select-none absolute -bottom-10 -right-16 w-[520px] max-w-none opacity-[0.08]"
      />
      <Card className="w-full max-w-sm border-slate-200 relative z-10">
        <CardHeader className="items-center text-center">
          <div className="h-12 w-12 rounded-md bg-[#002FA7] flex items-center justify-center mb-2">
            <GraduationCap size={26} weight="fill" color="#fff" />
          </div>
          <CardTitle className="font-display text-xl">LeadPulse</CardTitle>
          <CardDescription>Sign in to view weekly CRM reports</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="username" className="text-xs uppercase tracking-wide text-slate-500">
                Username
              </Label>
              <Input
                id="username"
                data-testid="login-username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1"
                autoComplete="username"
              />
            </div>
            <div>
              <Label htmlFor="password" className="text-xs uppercase tracking-wide text-slate-500">
                Password
              </Label>
              <Input
                id="password"
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1"
                autoComplete="current-password"
              />
            </div>
            {error && (
              <p className="text-sm text-red-600" data-testid="login-error">
                {error}
              </p>
            )}
            <Button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2"
              data-testid="login-submit"
            >
              <LockKey size={18} weight="bold" /> {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
