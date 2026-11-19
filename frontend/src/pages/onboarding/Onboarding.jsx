import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, store } from "../../lib";
import { baseDomain } from "../../util/tenant";
import LandingShell from "../landing/LandingShell";
import HeroDotField from "../landing/HeroDotField";
import Turnstile from "../../components/Turnstile";

// LP-002 guided onboarding wizard (route + card style, D-4). Chooser + 5 steps
// over the existing two-phase registration. The final step POSTs /register with
// the four fields it needs (email/password/subdomain/language) + name = the
// workspace (org) display name, and meta = { sector, org, adminName, place }:
// free-form context stored on Tenant.meta. The post-activation /configure step
// (B5) reads meta to create the first Organisation (from org), name the root
// administration unit (from place) and set the admin's name.
// ponytail: copy is hardcoded English for now; moves to per-locale JSON (D-9).
const DRAFT_KEY = "akvo_onboarding_draft";
const SUBDOMAIN_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const INPUT_STEPS = 5; // monitor, org, place, address, admin

const SECTORS = [
  { key: "water", label: "Water & sanitation" },
  { key: "health", label: "Health facilities" },
  { key: "agriculture", label: "Agriculture & farms" },
  { key: "education", label: "Education / schools" },
  { key: "other", label: "Something else" },
];

const EMPTY = {
  sector: "",
  org: "",
  place: "",
  subdomain: "",
  adminName: "",
  email: "",
};

const loadDraft = () => {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : { ...EMPTY };
  } catch (err) {
    return { ...EMPTY };
  }
};

const firstError = (value) => String(Array.isArray(value) ? value[0] : value);

const Onboarding = () => {
  const navigate = useNavigate();
  const activeLang = store.useState((s) => s.language.active);
  // Workspace language = the landing locale (en/es/fr all accepted, B6/D-10').
  const language = ["es", "fr"].includes(activeLang) ? activeLang : "en";
  const domain = baseDomain() || "mis.akvo.org";

  const [step, setStep] = useState(1); // 1..5 inputs · 6 done (no chooser)
  const [data, setData] = useState(loadDraft);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [avail, setAvail] = useState(null); // { available, reason } | null
  const [checking, setChecking] = useState(false);
  const siteKey = window?.appConfig?.turnstileSiteKey || "";
  const [captchaToken, setCaptchaToken] = useState("");
  const mounted = useRef(false);
  const availTimer = useRef(0);

  useEffect(() => {
    document.title = "Create your workspace";
  }, []);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    } catch (err) {
      // ignore storage failures (private mode, quota)
    }
  }, [data]);

  // Live availability check on the address step, debounced.
  useEffect(() => {
    setAvail(null);
    const v = data.subdomain.trim().toLowerCase();
    if (step !== 4 || v.length < 3 || !SUBDOMAIN_RE.test(v)) {
      return () => {};
    }
    setChecking(true);
    window.clearTimeout(availTimer.current);
    availTimer.current = window.setTimeout(() => {
      api
        .get(`register/subdomain?value=${encodeURIComponent(v)}`)
        .then((res) => setAvail(res.data))
        .catch(() => setAvail(null))
        .finally(() => setChecking(false));
    }, 450);
    return () => window.clearTimeout(availTimer.current);
  }, [data.subdomain, step]);

  const set = (key, value) => {
    setData((d) => ({ ...d, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  const validate = (which) => {
    const e = {};
    if (which === 1 && !data.sector) {
      e.sector = "Pick one to continue.";
    }
    if (which === 2 && !data.org.trim()) {
      e.org = "Enter your organisation name.";
    }
    if (which === 3 && !data.place.trim()) {
      e.place = "Enter the country or region.";
    }
    if (which === 4) {
      const v = data.subdomain.trim().toLowerCase();
      if (v.length < 3) {
        e.subdomain = "At least 3 characters.";
      } else if (!SUBDOMAIN_RE.test(v)) {
        e.subdomain = "Lowercase letters, digits and hyphens only.";
      } else if (avail && !avail.available) {
        e.subdomain = avail.reason || "That address is taken.";
      }
    }
    if (which === 5) {
      if (!data.adminName.trim()) {
        e.adminName = "Enter your name.";
      }
      if (!EMAIL_RE.test(data.email.trim())) {
        e.email = "Enter a valid email.";
      }
      if (password.length < 8) {
        e.password = "At least 8 characters.";
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const back = () => setStep((s) => Math.max(1, s - 1));

  const submit = () => {
    setSubmitting(true);
    const payload = {
      email: data.email.trim(),
      password,
      subdomain: data.subdomain.trim().toLowerCase(),
      language,
      name: data.org.trim(),
      captcha_token: captchaToken,
      meta: {
        sector: data.sector,
        org: data.org.trim(),
        adminName: data.adminName.trim(),
        place: data.place.trim(),
      },
    };
    api
      .post("register", payload)
      .then(() => {
        setPassword("");
        try {
          window.localStorage.removeItem(DRAFT_KEY);
        } catch (err) {
          // ignore
        }
        setStep(6);
      })
      .catch((err) => {
        // A Turnstile token is single-use; clear it so a retry re-solves.
        setCaptchaToken("");
        const details = err.response?.data?.details || {};
        const next = {};
        if (details.subdomain) {
          next.subdomain = firstError(details.subdomain);
        }
        if (details.email) {
          next.email = firstError(details.email);
        }
        if (details.password) {
          next.password = firstError(details.password);
        }
        setErrors(next);
        if (next.subdomain) {
          setStep(4);
        }
      })
      .finally(() => setSubmitting(false));
  };

  const advance = () => {
    if (!validate(step)) {
      return;
    }
    if (step === INPUT_STEPS) {
      submit();
      return;
    }
    setStep((s) => s + 1);
  };

  const pct = (step / (INPUT_STEPS + 1)) * 100;
  const err = (key) =>
    errors[key] ? (
      <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">
        {errors[key]}
      </p>
    ) : null;
  const inputCls =
    "mt-1 w-full rounded-lg border border-akvo-border bg-bg-secondary px-4 py-3 text-base text-text-primary outline-none focus:border-akvo dark:bg-white/5 dark:text-white";

  return (
    <LandingShell showCta={false}>
      <section className="relative flex flex-1 items-center justify-center overflow-hidden bg-akvo-deep px-4 py-12 sm:px-6">
        <HeroDotField interactive={false} />
        <div className="relative z-10 w-full max-w-xl rounded-2xl border border-akvo-border/50 bg-white p-6 shadow-xl dark:bg-bg-dark sm:p-8">
          <div className="flex items-center gap-4">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-akvo-light">
              <div
                className="h-full rounded-full bg-akvo transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <button
              type="button"
              aria-label="Close and return to the landing page"
              onClick={() => navigate("/")}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-secondary text-text-muted hover:bg-akvo-light hover:text-akvo-text dark:bg-white/10"
            >
              ✕
            </button>
          </div>

          {step >= 1 && step <= INPUT_STEPS ? (
            <div className="mt-6">
              <p className="font-mono text-sm uppercase tracking-wide text-akvo-text dark:text-akvo-bright">
                Step {step} of {INPUT_STEPS}
              </p>

              {step === 1 ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    What do you want to monitor?
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    Pick the closest — this shapes your starter forms.
                  </p>
                  <div className="mt-5 space-y-3">
                    {SECTORS.map((s) => (
                      <button
                        key={s.key}
                        type="button"
                        onClick={() => set("sector", s.key)}
                        className={
                          data.sector === s.key
                            ? "flex w-full items-center gap-3 rounded-xl border-2 border-akvo bg-akvo-light px-4 py-3 text-left font-semibold text-akvo-text"
                            : "flex w-full items-center gap-3 rounded-xl border border-akvo-border bg-bg-secondary px-4 py-3 text-left text-text-secondary hover:border-akvo dark:bg-white/5 dark:text-gray-300"
                        }
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                  {err("sector")}
                </>
              ) : null}

              {step === 2 ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    What’s your organisation called?
                  </h2>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Organisation name
                    <input
                      className={inputCls}
                      value={data.org}
                      onChange={(e) => set("org", e.target.value)}
                      placeholder="Rural Water Trust"
                    />
                  </label>
                  {err("org")}
                </>
              ) : null}

              {step === 3 ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    Where do you work?
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    The top place you report on — your first administrative
                    unit.
                  </p>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Country or region
                    <input
                      className={inputCls}
                      value={data.place}
                      onChange={(e) => set("place", e.target.value)}
                      placeholder="Kenya"
                    />
                  </label>
                  {err("place")}
                </>
              ) : null}

              {step === 4 ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    Choose your workspace address.
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    This is where your team signs in.
                  </p>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Workspace address
                    <span className="mt-1 flex items-stretch">
                      <input
                        className="w-full rounded-l-lg border border-akvo-border bg-bg-secondary px-4 py-3 text-base text-text-primary outline-none focus:border-akvo dark:bg-white/5 dark:text-white"
                        value={data.subdomain}
                        onChange={(e) =>
                          set(
                            "subdomain",
                            e.target.value.toLowerCase().replace(/\s/g, "")
                          )
                        }
                        placeholder="your-org"
                      />
                      <span className="flex items-center rounded-r-lg border border-l-0 border-akvo-border bg-akvo-light px-3 font-mono text-sm text-akvo-text">
                        .{domain}
                      </span>
                    </span>
                  </label>
                  {checking ? (
                    <p className="mt-1.5 text-sm text-text-muted dark:text-gray-400">
                      Checking availability…
                    </p>
                  ) : null}
                  {!checking && avail && avail.available ? (
                    <p className="mt-1.5 text-sm font-semibold text-akvo-text dark:text-akvo-bright">
                      ✓ Available
                    </p>
                  ) : null}
                  {!checking &&
                  avail &&
                  !avail.available &&
                  !errors.subdomain ? (
                    <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">
                      {avail.reason || "That address is taken."}
                    </p>
                  ) : null}
                  {err("subdomain")}
                </>
              ) : null}

              {step === 5 ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    Who’s the workspace admin?
                  </h2>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Your name
                    <input
                      className={inputCls}
                      value={data.adminName}
                      onChange={(e) => set("adminName", e.target.value)}
                      placeholder="Full name"
                    />
                  </label>
                  {err("adminName")}
                  <label className="mt-4 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Email
                    <input
                      className={inputCls}
                      type="email"
                      value={data.email}
                      onChange={(e) => set("email", e.target.value)}
                      placeholder="you@org.org"
                    />
                  </label>
                  {err("email")}
                  <label className="mt-4 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    Password
                    <input
                      className={inputCls}
                      type="password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        setErrors((x) => ({ ...x, password: "" }));
                      }}
                      placeholder="At least 8 characters"
                    />
                  </label>
                  {err("password")}
                  <Turnstile siteKey={siteKey} onToken={setCaptchaToken} />
                </>
              ) : null}

              <div className="mt-8 flex items-center justify-between gap-3">
                {step > 1 ? (
                  <button
                    type="button"
                    onClick={back}
                    className="rounded-full border border-akvo-border px-5 py-2.5 text-sm font-semibold text-text-secondary hover:bg-bg-secondary dark:text-gray-300"
                  >
                    Back
                  </button>
                ) : (
                  <span />
                )}
                <button
                  type="button"
                  onClick={advance}
                  disabled={submitting}
                  className="rounded-full bg-akvo px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-akvo-dark disabled:opacity-60"
                >
                  {step === INPUT_STEPS
                    ? submitting
                      ? "Creating…"
                      : "Create my workspace"
                    : "Continue"}
                </button>
              </div>
            </div>
          ) : null}

          {step === 6 ? (
            <div className="mt-6 py-8 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-akvo-light text-2xl text-akvo-text">
                ✓
              </div>
              <h2 className="mt-5 font-title text-2xl font-bold text-text-primary dark:text-white">
                Check your email to activate.
              </h2>
              <p className="mt-3 text-text-muted dark:text-gray-400">
                We’re creating{" "}
                <strong className="text-text-primary dark:text-white">
                  {data.subdomain}.{domain}
                </strong>{" "}
                and pre-configuring it from your answers. Click the activation
                link we just sent to{" "}
                <strong className="text-text-primary dark:text-white">
                  {data.email}
                </strong>
                .
              </p>
              <button
                type="button"
                onClick={() => navigate("/")}
                className="mt-8 rounded-full bg-akvo px-6 py-2.5 text-sm font-semibold text-white hover:bg-akvo-dark"
              >
                Done
              </button>
            </div>
          ) : null}
        </div>
      </section>
    </LandingShell>
  );
};

export default Onboarding;
