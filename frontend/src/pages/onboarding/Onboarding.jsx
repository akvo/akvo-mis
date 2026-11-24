import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, store } from "../../lib";
import { useTranslation, LANGS } from "../../lib/i18n";
import { baseDomain } from "../../util/tenant";
import LandingShell from "../landing/LandingShell";
import HeroDotField from "../landing/HeroDotField";
import Turnstile from "../../components/Turnstile";

// LP-002 guided onboarding wizard (route + card style, D-4), extended by LP-004
// with live Form Library categories and a starter-forms step. Six input steps
// over the existing two-phase registration:
//   1 category · 2 starter forms · 3 org · 4 place · 5 address · 6 admin
// The final step POSTs /register with the four fields it needs
// (email/password/subdomain/language) + name = the workspace (org) display
// name, and meta = { category, template_ids, org, adminName, place }: free-form
// context stored on Tenant.meta. The post-activation /configure step reads meta
// to create the first Organisation (org), name the root unit (place), set the
// admin's name, and clone the chosen library templates (template_ids) as drafts.
// Chrome strings come from the global i18n library (en/es/fr, en fallback):
// lib/i18n/<locale>/onboarding.json, read with useTranslation("onboarding").
const DRAFT_KEY = "akvo_onboarding_draft";
const SUBDOMAIN_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
// The ordered input steps — the single source of truth for the wizard. Render,
// validation and navigation key off these NAMES, never a literal step number,
// so inserting or reordering a step is a one-line change here (the done-screen
// collision bug came from hand-renumbering scattered literals).
const STEPS = [
  "category",
  "forms",
  "org",
  "place",
  "address",
  "language",
  "admin",
];
const INPUT_STEPS = STEPS.length;
// The "check your email to activate" screen, after a successful submit; derived
// so it always sits past the inputs and never collides with the last one.
const DONE_STEP = INPUT_STEPS + 1;
// 1-based step number for a key (0 if absent). FORMS is the skippable step; the
// address step runs the live availability check.
const stepNo = (key) => STEPS.indexOf(key) + 1;
const FORMS_STEP = stepNo("forms");
const ADDRESS_STEP = stepNo("address");
const MAX_STARTER_FORMS = 10; // mirrors RegisterSerializer.MAX_STARTER_FORMS
const SKIP = "skip"; // step-1 "Something else / skip" sentinel (distinct from
// null = untouched, so the step can require a deliberate choice)

const EMPTY = {
  category: null,
  template_ids: [],
  org: "",
  place: "",
  subdomain: "",
  adminName: "",
  email: "",
};

// A `?subdomain=` query param (e.g. the WorkspaceNotFound "Create this
// workspace" link) prefills the address field, sanitised like the input and
// winning over any stale draft value — the visitor arrived at that exact
// address on purpose.
const subdomainFromQuery = () => {
  try {
    const raw = new URLSearchParams(window.location.search).get("subdomain");
    return raw ? raw.toLowerCase().replace(/\s/g, "") : "";
  } catch (err) {
    return "";
  }
};

const loadDraft = () => {
  const fromQuery = subdomainFromQuery();
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    const base = raw ? { ...EMPTY, ...JSON.parse(raw) } : { ...EMPTY };
    return fromQuery ? { ...base, subdomain: fromQuery } : base;
  } catch (err) {
    return fromQuery ? { ...EMPTY, subdomain: fromQuery } : { ...EMPTY };
  }
};

const firstError = (value) => String(Array.isArray(value) ? value[0] : value);

const Onboarding = () => {
  const navigate = useNavigate();
  const c = useTranslation("onboarding");
  const activeLang = store.useState((s) => s.language.active);
  // Workspace language = the landing locale (en/es/fr all accepted, B6/D-10').
  const language = ["es", "fr"].includes(activeLang) ? activeLang : "en";
  const domain = baseDomain() || "mis.akvo.org";

  const [step, setStep] = useState(1); // 1..6 inputs · 7 done
  const [data, setData] = useState(loadDraft);
  const [categories, setCategories] = useState([]);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [avail, setAvail] = useState(null); // { available, reason } | null
  const [checking, setChecking] = useState(false);
  // The catalogue loads async; until it does we must not decide the
  // starter-forms step is empty (a draft could otherwise skip it yet still
  // submit saved template ids).
  const [catalogueLoaded, setCatalogueLoaded] = useState(false);
  // A request-level failure (captcha, throttle, 5xx, network) that maps to no
  // single field — shown near the submit button so the visitor is never stuck.
  const [formError, setFormError] = useState("");
  const siteKey = window?.appConfig?.turnstileSiteKey || "";
  const [captchaToken, setCaptchaToken] = useState("");
  // Bumped on a failed submit to reset the single-use Turnstile widget.
  const [captchaNonce, setCaptchaNonce] = useState(0);
  const mounted = useRef(false);

  useEffect(() => {
    document.title = c.title;
  }, [c.title]);

  // Fetch the starter-forms catalogue once. On any failure categories stay
  // empty, so step 1 shows just the skip tile and onboarding never dead-ends.
  useEffect(() => {
    api
      .get("register/form-library")
      .then((res) => setCategories(res.data?.categories || []))
      .catch(() => setCategories([]))
      .finally(() => setCatalogueLoaded(true));
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

  // Drop the saved draft once onboarding is complete (DONE_STEP is only reached
  // after a successful register). Declared AFTER the save effect so that if a
  // data-save and this run in the same commit, this one wins and the draft
  // never lingers — the removeItem in submit() alone can be clobbered by a
  // trailing save.
  useEffect(() => {
    if (step !== DONE_STEP) {
      return;
    }
    try {
      window.localStorage.removeItem(DRAFT_KEY);
    } catch (err) {
      // ignore storage failures
    }
  }, [step]);

  // Live availability check on the address step, debounced. The cleanup marks
  // this run superseded (`active = false`) so a slower in-flight request for an
  // old value can never apply its result to a newer one, and so "Checking…"
  // never sticks when the value becomes ineligible before the timer fires.
  useEffect(() => {
    const v = data.subdomain.trim().toLowerCase();
    const eligible =
      step === ADDRESS_STEP && v.length >= 3 && SUBDOMAIN_RE.test(v);
    setAvail(null);
    setChecking(eligible);
    if (!eligible) {
      return () => {};
    }
    let active = true;
    const timer = window.setTimeout(() => {
      api
        .get(`register/subdomain?value=${encodeURIComponent(v)}`)
        .then((res) => {
          if (active) {
            setAvail(res.data);
          }
        })
        .catch(() => {
          if (active) {
            setAvail(null);
          }
        })
        .finally(() => {
          if (active) {
            setChecking(false);
          }
        });
    }, 450);
    return () => {
      active = false;
      setChecking(false);
      window.clearTimeout(timer);
    };
  }, [data.subdomain, step]);

  const set = (key, value) => {
    setData((d) => ({ ...d, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  // Picking a category (or skip) resets the template selection: the ticked
  // ids belong to whichever category was open, and must not carry across.
  // Re-picking the SAME category keeps them — only an actual change clears.
  const chooseCategory = (value) => {
    setData((d) => {
      const sameCategory =
        d.category === value ||
        (d.category &&
          value &&
          typeof d.category === "object" &&
          typeof value === "object" &&
          d.category.id === value.id);
      if (sameCategory) {
        return d;
      }
      return { ...d, category: value, template_ids: [] };
    });
    setErrors((e) => ({ ...e, category: "" }));
  };

  // The workspace language is driven by store.language.active — the same state
  // the shared-shell header switch sets — so the dedicated step defaults to the
  // header's choice, keeps a single source of truth, and re-renders the wizard
  // in the chosen language. `language` derives from it for the register payload.
  const chooseLanguage = (code) => {
    store.update((s) => {
      s.language.active = code;
    });
  };

  const toggleTemplate = (id) => {
    setData((d) => {
      if (d.template_ids.includes(id)) {
        return { ...d, template_ids: d.template_ids.filter((x) => x !== id) };
      }
      if (d.template_ids.length >= MAX_STARTER_FORMS) {
        return d; // at the cap the backend would reject; stop adding here
      }
      return { ...d, template_ids: [...d.template_ids, id] };
    });
  };

  // The templates to show on step 2: the chosen category's, or none (skip,
  // an unknown category, or a category with no published templates).
  const chosenCategory =
    data.category && data.category !== SKIP ? data.category : null;
  const chosenTemplates = chosenCategory
    ? categories.find((x) => x.id === chosenCategory.id)?.templates || []
    : [];

  // The current step's key, derived from STEPS; render and validation switch on
  // this name, never a raw step number.
  const stepKey = STEPS[step - 1];

  const validate = (which) => {
    const key = STEPS[which - 1];
    const e = {};
    if (key === "category" && !data.category) {
      e.category = c.categoryRequired;
    }
    // The "forms" (starter forms) step is opt-in: an empty selection is valid.
    if (key === "org" && !data.org.trim()) {
      e.org = c.orgRequired;
    }
    if (key === "place" && !data.place.trim()) {
      e.place = c.placeRequired;
    }
    if (key === "address") {
      const v = data.subdomain.trim().toLowerCase();
      if (v.length < 3) {
        e.subdomain = c.addressMin;
      } else if (!SUBDOMAIN_RE.test(v)) {
        e.subdomain = c.addressPattern;
      } else if (avail && !avail.available) {
        e.subdomain = avail.reason || c.addressTaken;
      }
    }
    if (key === "admin") {
      if (!data.adminName.trim()) {
        e.adminName = c.nameRequired;
      }
      if (!EMAIL_RE.test(data.email.trim())) {
        e.email = c.emailInvalid;
      }
      if (password.length < 8) {
        e.password = c.passwordMin;
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  // The starter-forms step is skipped when there is nothing to pick: the
  // "Something else / skip" tile, or a chosen category the *loaded* catalogue
  // shows has no templates. Before the catalogue loads we do NOT skip — a
  // returning visitor's draft must not leap past the step yet still submit the
  // template ids it saved (H). Navigation jumps across FORMS_STEP both ways.
  const skipForms =
    data.category === SKIP || (catalogueLoaded && chosenTemplates.length === 0);

  // When the forms step is auto-skipped, renumber the UI so the user sees a
  // contiguous count (no missing step) instead of a jump. The internal `step`
  // index is unchanged — it still drives which screen renders.
  const totalSteps = skipForms ? INPUT_STEPS - 1 : INPUT_STEPS;
  const displayStep = skipForms && step > FORMS_STEP ? step - 1 : step;

  const back = () =>
    setStep((s) =>
      Math.max(1, s === FORMS_STEP + 1 && skipForms ? FORMS_STEP - 1 : s - 1)
    );

  const submit = () => {
    setSubmitting(true);
    setFormError("");
    const payload = {
      email: data.email.trim(),
      password,
      subdomain: data.subdomain.trim().toLowerCase(),
      language,
      name: data.org.trim(),
      captcha_token: captchaToken,
      meta: {
        category: chosenCategory,
        // Only submit ids that belong to the chosen (loaded) category, so a
        // stale draft id for another category is never cloned (H).
        template_ids: data.template_ids.filter((id) =>
          chosenTemplates.some((t) => t.id === id)
        ),
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
        setStep(DONE_STEP);
      })
      .catch((err) => {
        // A Turnstile token is single-use; clear it and reset the widget so a
        // retry solves a fresh challenge instead of re-sending an empty token.
        setCaptchaToken("");
        setCaptchaNonce((n) => n + 1);
        const res = err.response;
        const details = res?.data?.details || {};
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
        // The org display name is submitted as `name`; show its error on the
        // organisation step.
        if (details.name) {
          next.org = firstError(details.name);
        }
        setErrors(next);
        // Send the visitor back to the step that owns the failing field.
        if (next.subdomain) {
          setStep(ADDRESS_STEP);
        } else if (next.org) {
          setStep(stepNo("org"));
        }
        // No field-level detail (captcha, meta, throttle, 5xx, network): show a
        // message near the button so Create is never silently re-enabled with
        // no explanation.
        if (!Object.keys(next).length) {
          let msg = res?.data?.message || res?.data?.detail;
          if (!msg) {
            if (!res) {
              msg = c.errorNetwork;
            } else if (res.status === 429) {
              msg = c.errorRateLimited;
            } else if (res.status >= 500) {
              msg = c.errorServer;
            } else {
              msg = c.errorGeneric;
            }
          }
          setFormError(msg);
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
    setStep((s) =>
      s === FORMS_STEP - 1 && skipForms ? FORMS_STEP + 1 : s + 1
    );
  };

  const pct = (displayStep / (totalSteps + 1)) * 100;
  const err = (key) =>
    errors[key] ? (
      <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">
        {errors[key]}
      </p>
    ) : null;
  const inputCls =
    "mt-1 w-full rounded-lg border border-brand-border bg-bg-secondary px-4 py-3 text-base text-text-primary outline-none focus:border-brand dark:bg-white/5 dark:text-white";
  const tileCls = (selected) =>
    selected
      ? "flex w-full items-center gap-3 rounded-xl border-2 border-brand bg-brand-light px-4 py-3 text-left font-semibold text-brand-text"
      : "flex w-full items-center gap-3 rounded-xl border border-brand-border bg-bg-secondary px-4 py-3 text-left text-text-secondary hover:border-brand dark:bg-white/5 dark:text-gray-300";

  return (
    <LandingShell showCta={false}>
      <section className="relative flex flex-1 items-center justify-center overflow-hidden bg-brand-deep px-4 py-12 sm:px-6">
        <HeroDotField interactive={false} />
        <div className="relative z-10 w-full max-w-xl rounded-2xl border border-brand-border/50 bg-white p-6 shadow-xl dark:bg-bg-dark sm:p-8">
          <div className="flex items-center gap-4">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-brand-light">
              <div
                className="h-full rounded-full bg-brand transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <button
              type="button"
              aria-label={c.close}
              onClick={() => navigate("/")}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-secondary text-text-muted hover:bg-brand-light hover:text-brand-text dark:bg-white/10"
            >
              ✕
            </button>
          </div>

          {step >= 1 && step <= INPUT_STEPS ? (
            <div className="mt-6">
              <p className="font-mono text-sm uppercase tracking-wide text-brand-text dark:text-brand-bright">
                {c.stepPrefix} {displayStep} {c.stepJoin} {totalSteps}
              </p>

              {stepKey === "category" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.monitorTitle}
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    {c.monitorHint}
                  </p>
                  <div className="mt-5 space-y-3">
                    {categories.map((cat) => (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() =>
                          chooseCategory({
                            id: cat.id,
                            name: cat.name,
                            slug: cat.slug,
                          })
                        }
                        aria-pressed={Boolean(
                          chosenCategory && chosenCategory.id === cat.id
                        )}
                        className={tileCls(
                          chosenCategory && chosenCategory.id === cat.id
                        )}
                      >
                        {cat.name}
                      </button>
                    ))}
                    <button
                      type="button"
                      aria-pressed={data.category === SKIP}
                      onClick={() => chooseCategory(SKIP)}
                      className={tileCls(data.category === SKIP)}
                    >
                      {c.skipTile}
                    </button>
                  </div>
                  {err("category")}
                </>
              ) : null}

              {stepKey === "forms" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.formsTitle}
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    {c.formsHint}
                  </p>
                  {chosenTemplates.length > 0 ? (
                    <div className="mt-5 space-y-3">
                      {chosenTemplates.map((t) => {
                        const ticked = data.template_ids.includes(t.id);
                        return (
                          <button
                            key={t.id}
                            type="button"
                            aria-pressed={ticked}
                            onClick={() => toggleTemplate(t.id)}
                            className={tileCls(ticked)}
                          >
                            <span
                              className={
                                ticked
                                  ? "flex h-5 w-5 items-center justify-center rounded border-2 border-brand bg-brand text-xs text-white"
                                  : "flex h-5 w-5 items-center justify-center rounded border-2 border-brand-border text-xs"
                              }
                            >
                              {ticked ? "✓" : ""}
                            </span>
                            <span className="flex-1">{t.name}</span>
                            {t.monitoring_count > 0 ? (
                              <span className="rounded-full bg-brand-light px-2 py-0.5 font-mono text-xs text-brand-text">
                                +{t.monitoring_count} {c.monitoring}
                              </span>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-5 rounded-xl border border-brand-border bg-bg-secondary px-4 py-3 text-text-muted dark:bg-white/5 dark:text-gray-400">
                      {c.formsEmpty}
                    </p>
                  )}
                </>
              ) : null}

              {stepKey === "org" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.orgTitle}
                  </h2>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.orgLabel}
                    <input
                      className={inputCls}
                      value={data.org}
                      onChange={(e) => set("org", e.target.value)}
                      placeholder={c.orgPlaceholder}
                    />
                  </label>
                  {err("org")}
                </>
              ) : null}

              {stepKey === "place" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.placeTitle}
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    {c.placeHint}
                  </p>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.placeLabel}
                    <input
                      className={inputCls}
                      value={data.place}
                      onChange={(e) => set("place", e.target.value)}
                      placeholder={c.placePlaceholder}
                    />
                  </label>
                  {err("place")}
                </>
              ) : null}

              {stepKey === "address" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.addressTitle}
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    {c.addressHint}
                  </p>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.addressLabel}
                    <span className="mt-1 flex items-stretch">
                      <input
                        className="w-full rounded-l-lg border border-brand-border bg-bg-secondary px-4 py-3 text-base text-text-primary outline-none focus:border-brand dark:bg-white/5 dark:text-white"
                        value={data.subdomain}
                        onChange={(e) =>
                          set(
                            "subdomain",
                            e.target.value.toLowerCase().replace(/\s/g, "")
                          )
                        }
                        placeholder={c.addressPlaceholder}
                      />
                      <span className="flex items-center rounded-r-lg border border-l-0 border-brand-border bg-brand-light px-3 font-mono text-sm text-brand-text">
                        .{domain}
                      </span>
                    </span>
                  </label>
                  {checking ? (
                    <p className="mt-1.5 text-sm text-text-muted dark:text-gray-400">
                      {c.addressChecking}
                    </p>
                  ) : null}
                  {!checking && avail && avail.available ? (
                    <p className="mt-1.5 text-sm font-semibold text-brand-text dark:text-brand-bright">
                      {c.addressAvailable}
                    </p>
                  ) : null}
                  {!checking &&
                  avail &&
                  !avail.available &&
                  !errors.subdomain ? (
                    <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">
                      {avail.reason || c.addressTaken}
                    </p>
                  ) : null}
                  {err("subdomain")}
                </>
              ) : null}

              {stepKey === "language" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.languageTitle}
                  </h2>
                  <p className="mt-1 text-text-muted dark:text-gray-400">
                    {c.languageHint}
                  </p>
                  <div className="mt-5 space-y-3">
                    {LANGS.map((l) => (
                      <button
                        key={l.code}
                        type="button"
                        aria-pressed={language === l.code}
                        onClick={() => chooseLanguage(l.code)}
                        className={tileCls(language === l.code)}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}

              {stepKey === "admin" ? (
                <>
                  <h2 className="mt-2 font-title text-2xl font-bold text-text-primary dark:text-white">
                    {c.adminTitle}
                  </h2>
                  <label className="mt-5 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.nameLabel}
                    <input
                      className={inputCls}
                      value={data.adminName}
                      onChange={(e) => set("adminName", e.target.value)}
                      placeholder={c.namePlaceholder}
                    />
                  </label>
                  {err("adminName")}
                  <label className="mt-4 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.emailLabel}
                    <input
                      className={inputCls}
                      type="email"
                      value={data.email}
                      onChange={(e) => set("email", e.target.value)}
                      placeholder={c.emailPlaceholder}
                    />
                  </label>
                  {err("email")}
                  <label className="mt-4 block text-sm font-semibold text-text-secondary dark:text-gray-300">
                    {c.passwordLabel}
                    <input
                      className={inputCls}
                      type="password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        setErrors((x) => ({ ...x, password: "" }));
                      }}
                      placeholder={c.passwordPlaceholder}
                    />
                  </label>
                  {err("password")}
                  <Turnstile
                    siteKey={siteKey}
                    onToken={setCaptchaToken}
                    resetSignal={captchaNonce}
                  />
                </>
              ) : null}

              {formError ? (
                <p
                  role="alert"
                  className="mt-4 rounded-lg border border-red-300 bg-red-50 px-4 py-2.5 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-400"
                >
                  {formError}
                </p>
              ) : null}

              <div className="mt-8 flex items-center justify-between gap-3">
                {step > 1 ? (
                  <button
                    type="button"
                    onClick={back}
                    className="rounded-full border border-brand-border px-5 py-2.5 text-sm font-semibold text-text-secondary hover:bg-bg-secondary dark:text-gray-300"
                  >
                    {c.back}
                  </button>
                ) : (
                  <span />
                )}
                <button
                  type="button"
                  onClick={advance}
                  disabled={submitting}
                  className="rounded-full bg-brand px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-dark disabled:opacity-60"
                >
                  {step === INPUT_STEPS
                    ? submitting
                      ? c.creating
                      : c.create
                    : c.continue}
                </button>
              </div>

              {/* Returning users land here from the landing CTA too; give them
                  a way to reach their existing workspace (D-4a). */}
              <p className="mt-6 text-center text-sm text-text-muted dark:text-gray-400">
                {c.haveWorkspace}{" "}
                <Link
                  to="/find-workspace"
                  className="font-semibold text-brand-text hover:underline dark:text-brand-bright"
                >
                  {c.findWorkspaceLink}
                </Link>
              </p>
            </div>
          ) : null}

          {step === DONE_STEP ? (
            <div className="mt-6 py-8 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-brand-light text-2xl text-brand-text">
                ✓
              </div>
              <h2 className="mt-5 font-title text-2xl font-bold text-text-primary dark:text-white">
                {c.doneTitle}
              </h2>
              <p className="mt-3 text-text-muted dark:text-gray-400">
                {c.doneCreating}{" "}
                <strong className="text-text-primary dark:text-white">
                  {data.subdomain}.{domain}
                </strong>{" "}
                {c.doneSentTo}{" "}
                <strong className="text-text-primary dark:text-white">
                  {data.email}
                </strong>
                .
              </p>
              <button
                type="button"
                onClick={() => navigate("/")}
                className="mt-8 rounded-full bg-brand px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark"
              >
                {c.done}
              </button>
            </div>
          ) : null}
        </div>
      </section>
    </LandingShell>
  );
};

export default Onboarding;
