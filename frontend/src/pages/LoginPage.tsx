import { FormEvent, useState } from "react";

interface LoginPageProps {
  error: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ error, onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onLogin(username, password);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-card">
        <div className="login-brand"><img src="/brand/sentrix-logo.png" alt="Sentrix" /></div>
        <p className="eyebrow">Observability & Monitoring</p>
        <h1>Sign in</h1>
        <p className="muted">Secure access to your organizations, projects, and observability workspaces.</p>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Username
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error && <div className="error" role="alert">{error}</div>}
          <button className="button" disabled={submitting} type="submit">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
