import { useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { ThemeToggle } from "../components/ThemeToggle";
import "./LandingPage.css";

const GITHUB_URL = "https://github.com/vallaksa/Dev-strom";

const QUICK_START = `git clone <repo-url>
cd Dev-Strom
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.api:api --reload`;

/* ── icons ──────────────────────────────────────────────────────────────── */
const svg = (d: string) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
    <path d={d} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IdeaIcon = () =>
  svg("M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.5.4.8.9.9 1.5H14.6c.1-.6.4-1.1.9-1.5A6 6 0 0 0 12 3Z");
const ScanIcon = () => svg("M10.5 17a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13ZM20 20l-4.9-4.9");
const CheckIcon = () => svg("M4 5h16M4 12h16M4 19h9M15.5 18l2 2 4-4");
const RocketIcon = () =>
  svg("M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M9 15l-3-3a12 12 0 0 1 8-9c3 0 5 2 5 5a12 12 0 0 1-9 8l-3-3Z");
const FileIcon = () => svg("M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7l-4-4ZM14 3v4h4");
const CopyIcon = () =>
  svg("M9 9h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1ZM5 15H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v1");

function LogoMark() {
  return (
    <img src="/logo-mark.svg" alt="" className="landing__mark" width="28" height="28" />
  );
}

export function LandingPage() {
  const navigate = useNavigate();
  const [stack, setStack] = useState("");
  const [copied, setCopied] = useState(false);

  const handleGenerate = (e: FormEvent) => {
    e.preventDefault();
    const q = stack.trim();
    navigate(q ? `/ideas?intent=${encodeURIComponent(q)}` : "/ideas");
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(QUICK_START);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked — no-op */
    }
  };

  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-nav__inner">
          <Link to="/" className="landing-nav__brand">
            <LogoMark />
            <span>Dev&#8209;Strom</span>
          </Link>
          <nav className="landing-nav__links">
            <NavLink to="/ideas" className="landing-nav__link">Ideas</NavLink>
            <NavLink to="/advisor" className="landing-nav__link">Repository Intelligence</NavLink>
            <a href={GITHUB_URL} className="landing-nav__link" target="_blank" rel="noreferrer">
              GitHub
            </a>
          </nav>
          <div className="landing-nav__cta">
            <Link to="/login" className="landing-nav__link landing-nav__signin">
              Sign in
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="landing-main">
        {/* ── hero ─────────────────────────────────────────────── */}
        <section className="landing-hero">
          <img src="/banner.png" alt="Dev-Strom" className="landing-hero__banner" />
          <h1 className="landing-hero__title">From tech stack to implementation plan</h1>
          <p className="landing-hero__lede">
            Get concrete project ideas for any tech stack, and analyze repositories with
            evidence-backed findings.
          </p>

          <form className="landing-terminal" onSubmit={handleGenerate}>
            <div className="landing-terminal__field">
              <span className="landing-terminal__prompt">$</span>
              <input
                className="landing-terminal__input"
                value={stack}
                onChange={(e) => setStack(e.target.value)}
                placeholder="Enter your stack (e.g. LangChain, FastAPI)"
                autoComplete="off"
                spellCheck={false}
                aria-label="Your tech stack"
              />
            </div>
            <button type="submit" className="btn btn-primary landing-terminal__go">
              Get Started
            </button>
          </form>
        </section>

        {/* ── dual-track features ──────────────────────────────── */}
        <section className="landing-bento">
          <article className="landing-card">
            <div className="landing-card__head">
              <span className="landing-card__glyph"><IdeaIcon /></span>
              <h2>The Idea Engine</h2>
            </div>
            <p>
              Searches the web for real-world problems and returns evidence-backed plans.
              Enter a stack, and Dev-Strom suggests project ideas — each with a problem
              statement, real-world value, and a detailed implementation plan ready for
              execution.
            </p>
            <div className="landing-card__chips">
              <span className="landing-chip">Sonar</span>
              <span className="landing-chip">Tavily</span>
            </div>
          </article>

          <article className="landing-card">
            <div className="landing-card__head">
              <span className="landing-card__glyph landing-card__glyph--steel"><ScanIcon /></span>
              <h2>Repository Intelligence</h2>
            </div>
            <p>
              Clones, parses, and analyzes repositories. Returns an evidence-first analysis
              with file/line citations, ranked recommendations, and an interactive
              architecture graph to understand complex codebases instantly.
            </p>
            <div className="landing-card__chips">
              <span className="landing-chip">AST parse</span>
              <span className="landing-chip">Architecture graph</span>
              <span className="landing-chip">LLM</span>
            </div>
          </article>
        </section>

        {/* ── evidence-first mockup ────────────────────────────── */}
        <section className="landing-section">
          <h2 className="landing-section__title">
            <span className="landing-section__icon"><CheckIcon /></span>
            Evidence-first analysis
          </h2>

          <div className="landing-mock">
            <div className="landing-mock__bar">
              <span className="landing-mock__dot" />
              <span className="landing-mock__dot" />
              <span className="landing-mock__dot" />
              <span className="landing-mock__path">devstrom / run_id: a8f92b…</span>
            </div>
            <div className="landing-mock__body">
              <div className="landing-mock__findings">
                <p className="mono-label">Critical findings</p>
                <div className="landing-finding landing-finding--high">
                  <div className="landing-finding__head">
                    <span className="landing-finding__name">Unbounded query execution</span>
                    <span className="badge badge-high">High impact</span>
                  </div>
                  <p>
                    Database queries in the analytics endpoint lack pagination, potentially
                    causing OOM errors on large datasets.
                  </p>
                  <span className="landing-finding__loc">
                    <FileIcon /> app/api/analytics.py:142
                  </span>
                </div>
                <div className="landing-finding landing-finding--med">
                  <div className="landing-finding__head">
                    <span className="landing-finding__name">Hardcoded auth tokens</span>
                    <span className="badge">Medium impact</span>
                  </div>
                  <p>
                    Test credentials are hardcoded in the testing suite setup, which might
                    leak into production if not stripped.
                  </p>
                  <span className="landing-finding__loc">
                    <FileIcon /> tests/conftest.py:28
                  </span>
                </div>
              </div>
              <div className="landing-mock__recs">
                <p className="mono-label">Ranked recommendations</p>
                <ol>
                  <li>
                    <span className="landing-rec__n">1</span>
                    <span>
                      Implement cursor pagination
                      <em>Effort: Low · Impact: High</em>
                    </span>
                  </li>
                  <li>
                    <span className="landing-rec__n landing-rec__n--accent">2</span>
                    <span>
                      Migrate secrets to <code>.env</code>
                      <em>Effort: Low · Impact: Medium</em>
                    </span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        </section>

        {/* ── quick start ──────────────────────────────────────── */}
        <section className="landing-section">
          <h2 className="landing-section__title">
            <span className="landing-section__icon"><RocketIcon /></span>
            Quick start
          </h2>
          <div className="landing-code">
            <div className="landing-code__bar">
              <span className="mono-label">bash</span>
              <button type="button" className="landing-code__copy" onClick={copy}>
                <CopyIcon />
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="landing-code__pre dark-scroll">
              <code>{QUICK_START}</code>
            </pre>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <Link to="/" className="landing-nav__brand">
          <LogoMark />
          <span>Dev&#8209;Strom</span>
        </Link>
        <nav className="landing-footer__links">
          <a href={GITHUB_URL} className="landing-nav__link" target="_blank" rel="noreferrer">
            GitHub
          </a>
          <Link to="/ideas" className="landing-nav__link">Ideas</Link>
          <Link to="/advisor" className="landing-nav__link">Repository Intelligence</Link>
        </nav>
        <p className="landing-footer__copy">
          © {new Date().getFullYear()} Dev-Strom · You've learned the stack. Now build
          something with it.
        </p>
      </footer>
    </div>
  );
}
