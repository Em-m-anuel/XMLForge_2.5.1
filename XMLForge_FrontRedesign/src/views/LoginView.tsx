import { useState } from "react";
import { Icon } from "../components/Icon";
import { Button, Field, Input, Key } from "../components/ui";
import { useStore } from "../store";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Mode = "login" | "register";

export function LoginView() {
  const { login, register, serverHealth } = useStore();
  const [mode, setMode] = useState<Mode>("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setSuccess(null);
    setPassword("");
    setConfirm("");
    if (next === "register") {
      setName("");
      setEmail("");
    }
  };

  const submitLogin = async () => {
    if (!email.trim() || !password) {
      setError("Email et mot de passe requis");
      return;
    }
    if (!EMAIL_RE.test(email.trim())) {
      setError("Format d'email invalide");
      return;
    }
    setBusy(true);
    setError(null);
    const res = await login(email.trim(), password);
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
  };

  const submitRegister = async () => {
    const fullName = name.trim();
    const mail = email.trim();
    if (!fullName) {
      setError("Le nom complet est requis");
      return;
    }
    if (fullName.length < 2) {
      setError("Le nom doit contenir au moins 2 caractères");
      return;
    }
    if (!mail) {
      setError("L'email est requis");
      return;
    }
    if (!EMAIL_RE.test(mail)) {
      setError("Format d'email invalide");
      return;
    }
    if (!password) {
      setError("Le mot de passe est requis");
      return;
    }
    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }
    if (password !== confirm) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }

    setBusy(true);
    setError(null);
    const res = await register(fullName, mail, password);
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setPassword("");
    setConfirm("");
    setSuccess("Compte créé. Vous pouvez maintenant vous connecter.");
  };

  return (
    <div className="grid-lines flex min-h-screen items-center justify-center bg-bg px-6">
      <div className="anim-up w-full max-w-[400px]">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#2f3b48] bg-[#101820] text-accent">
            <Icon name="braces" size={20} strokeWidth={1.8} />
          </span>
          <h1 className="mt-3 text-[20px] font-semibold tracking-tight text-fg">
            XML<span className="text-muted">Forge</span>
          </h1>
          <p className="mt-1 text-[12.5px] text-muted">Moteur de base de données · 100% XML</p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-[0_24px_70px_-25px_rgba(0,0,0,0.9)]">
          <div className="mb-4">
            <h2 className="text-[14.5px] font-semibold tracking-tight text-fg">
              {mode === "login" ? "Connexion" : "Créer votre compte"}
            </h2>
            <p className="mt-0.5 text-[12px] text-muted">
              {mode === "login"
                ? "Ouvrez une session locale sur ce poste."
                : "Un compte local pour travailler avec le moteur XML."}
            </p>
          </div>

          {success ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2 rounded-md border border-ok/30 bg-ok-soft px-3 py-2.5 text-[12.5px] text-ok">
                <Icon name="checkCircle" size={14} className="mt-px shrink-0" />
                <span>{success}</span>
              </div>
              <Button
                type="button"
                variant="primary"
                size="md"
                className="w-full"
                onClick={() => {
                  setSuccess(null);
                  switchMode("login");
                }}
              >
                Retour à la connexion
              </Button>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (mode === "login") void submitLogin();
                else void submitRegister();
              }}
              className="space-y-3.5"
            >
              {mode === "register" && (
                <Field label="Nom complet" required>
                  <Input
                    autoFocus
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Emmanuel Nyx"
                    autoComplete="name"
                  />
                </Field>
              )}
              <Field label="Email" required>
                <Input
                  autoFocus={mode === "login"}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@xmlforge.io"
                  autoComplete="email"
                />
              </Field>
              <Field label="Mot de passe" required>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                />
              </Field>
              {mode === "register" && (
                <Field label="Confirmation" required>
                  <Input
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                  />
                </Field>
              )}

              {error && (
                <p className="flex items-center gap-1.5 text-[12px] text-danger">
                  <Icon name="alert" size={12} />
                  {error}
                </p>
              )}

              <Button type="submit" variant="primary" size="md" loading={busy} className="w-full">
                {mode === "login" ? "Se connecter" : "Créer un compte"}
              </Button>
            </form>
          )}

          {!success && (
            <p className="mt-4 border-t border-line pt-3.5 text-center text-[12px] text-muted">
              {mode === "login" ? (
                <>
                  Pas de compte ?{" "}
                  <button
                    type="button"
                    className="font-medium text-accent hover:underline"
                    onClick={() => switchMode("register")}
                  >
                    Créer un compte
                  </button>
                </>
              ) : (
                <>
                  Déjà un compte ?{" "}
                  <button
                    type="button"
                    className="font-medium text-accent hover:underline"
                    onClick={() => switchMode("login")}
                  >
                    Se connecter
                  </button>
                </>
              )}
            </p>
          )}

          <div className="mt-4 flex items-center gap-2 border-t border-line pt-3.5 text-[11.5px] text-dim">
            <Icon name="hdd" size={12} />
            Stockage XML natif · {serverHealth?.storage?.data_plane || "XML"}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-center gap-4 text-[11px] text-dim">
          <span className="flex items-center gap-1.5">
            <Key>↵</Key> {mode === "login" ? "connexion" : "créer"}
          </span>
          <span className="flex items-center gap-1.5">
            <Icon name="cpu" size={11} />
            {serverHealth?.version || "5.0.0"}
          </span>
        </div>
      </div>
    </div>
  );
}
