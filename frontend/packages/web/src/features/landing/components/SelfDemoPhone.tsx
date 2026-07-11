import type { MotionValue } from "framer-motion";
import { motion, useTransform, useSpring, useMotionValue, useReducedMotion } from "framer-motion";

/**
 * The hero "self-demoing" phone.
 *
 * As the hero scrolls (driven by `progress`, 0→1), the device rotates from a
 * tilted 3D pose to face-on and its screen scrubs through the product flow —
 * Dashboard → Real Wealth → AI Signal — cross-fading continuously. Silent: no
 * captions or step rail (that's the job of the How-it-works section).
 *
 * The screen deliberately stays dark (it's a product screenshot of the app in
 * dark mode) regardless of the landing's light/dark theme.
 *
 * Falls back to a static first scene when `prefers-reduced-motion` is set.
 */

const T = "#00d4aa"; // brand teal
const BEAR = "#ff5b6a";

export function SelfDemoPhone({
  progress,
  className,
}: {
  progress?: MotionValue<number>;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const fallback = useMotionValue(0);
  const p = progress ?? fallback;

  // Device settles from tilted → face-on over the first third of the scroll.
  const ryRaw = useTransform(p, [0, 0.32], [-18, 0]);
  const scaleRaw = useTransform(p, [0, 0.32], [0.93, 1]);
  const ry = useSpring(ryRaw, { stiffness: 90, damping: 24, mass: 0.5 });
  const scale = useSpring(scaleRaw, { stiffness: 90, damping: 24, mass: 0.5 });

  // Continuous cross-fade between the three scenes.
  const o0 = useTransform(p, [0, 0.26, 0.36], [1, 1, 0]);
  const o1 = useTransform(p, [0.26, 0.36, 0.56, 0.66], [0, 1, 1, 0]);
  const o2 = useTransform(p, [0.56, 0.66, 1], [0, 1, 1]);
  const y0 = useTransform(p, [0, 0.36], [0, -18]);
  const y1 = useTransform(p, [0.26, 0.66], [16, -16]);
  const y2 = useTransform(p, [0.56, 1], [16, 0]);

  const rot = reduce ? 0 : ry;
  const scl = reduce ? 1 : scale;

  return (
    <div className={className} style={{ perspective: 1400 }}>
      <motion.div
        style={{
          rotateY: rot,
          scale: scl,
          width: 288,
          height: 592,
          borderRadius: 46,
          padding: 12,
          margin: "0 auto",
          transformStyle: "preserve-3d",
          background: "linear-gradient(150deg,#26314f 0%,#0c1220 62%)",
          boxShadow:
            "0 50px 100px -34px rgba(0,0,0,0.85), 0 0 0 1.5px rgba(255,255,255,0.07), inset 0 1px 1px rgba(255,255,255,0.14)",
        }}
        className="animate-[phoneFloat_6s_ease-in-out_infinite]"
      >
        {/* screen */}
        <div
          style={{
            position: "relative",
            width: "100%",
            height: "100%",
            borderRadius: 36,
            overflow: "hidden",
            background: "#070b14",
            fontFamily: "Inter, sans-serif",
            color: "#f2f6fd",
          }}
        >
          {/* notch + status bar */}
          <div
            style={{
              position: "absolute",
              top: 9,
              left: "50%",
              transform: "translateX(-50%)",
              width: 92,
              height: 22,
              background: "#02040a",
              borderRadius: "0 0 13px 13px",
              zIndex: 20,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: 38,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 22px",
              fontSize: 11,
              fontWeight: 600,
              color: "#93a6c2",
              zIndex: 15,
            }}
          >
            <span>9:41</span>
            <span style={{ color: T }}>◉ NafaIQ</span>
          </div>

          {/* scenes */}
          <Scene o={reduce ? undefined : o0} y={reduce ? undefined : y0} show={!!reduce}>
            <SceneDashboard />
          </Scene>
          <Scene o={reduce ? undefined : o1} y={reduce ? undefined : y1}>
            <SceneRealWealth />
          </Scene>
          <Scene o={reduce ? undefined : o2} y={reduce ? undefined : y2}>
            <SceneSignal />
          </Scene>

          {/* subtle screen glare */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 36,
              pointerEvents: "none",
              zIndex: 30,
              background:
                "linear-gradient(135deg, rgba(255,255,255,0.08), transparent 32%, transparent 72%, rgba(255,255,255,0.03))",
            }}
          />
        </div>
      </motion.div>

      <style>{`@keyframes phoneFloat{0%,100%{translate:0 0}50%{translate:0 -8px}}
@media (prefers-reduced-motion: reduce){.animate-\\[phoneFloat_6s_ease-in-out_infinite\\]{animation:none!important}}`}</style>
    </div>
  );
}

function Scene({
  o,
  y,
  show,
  children,
}: {
  o?: MotionValue<number>;
  y?: MotionValue<number>;
  show?: boolean;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      style={{
        position: "absolute",
        inset: 0,
        padding: "48px 15px 16px",
        opacity: o ?? (show ? 1 : 0),
        y: y ?? 0,
        willChange: "opacity, transform",
      }}
    >
      {children}
    </motion.div>
  );
}

/* ---- scene chrome helpers ---- */
const panel: React.CSSProperties = {
  background: "#0e1626",
  border: "1px solid rgba(255,255,255,0.07)",
  borderRadius: 14,
};
function Head({ t, pill, pillC = T }: { t: string; pill?: string; pillC?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 13,
      }}
    >
      <span style={{ fontSize: 15, fontWeight: 800, letterSpacing: "-0.01em" }}>{t}</span>
      {pill && (
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: pillC,
            background: "rgba(0,212,170,0.12)",
            padding: "5px 9px",
            borderRadius: 20,
          }}
        >
          {pill}
        </span>
      )}
    </div>
  );
}

function SceneDashboard() {
  const rows = [
    ["HBL", "Habib Bank", "142.60", "+2.1%", true],
    ["ENGRO", "Engro Corp", "298.40", "-0.8%", false],
    ["LUCK", "Lucky Cement", "712.15", "+3.4%", true],
  ] as const;
  return (
    <>
      <Head t="Dashboard" pill="KSE100 ▲ 1.24%" />
      <div style={{ ...panel, padding: 14, marginBottom: 10 }}>
        <div
          style={{ fontSize: 10, color: "#5c7191", textTransform: "uppercase", letterSpacing: 0.5 }}
        >
          Net worth · real
        </div>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginTop: 3 }}>
          PKR 3.05M
        </div>
        <svg
          viewBox="0 0 250 40"
          width="100%"
          height="40"
          style={{ marginTop: 6, display: "block" }}
        >
          <defs>
            <linearGradient id="sdg" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="rgba(0,212,170,.28)" />
              <stop offset="1" stopColor="rgba(0,212,170,0)" />
            </linearGradient>
          </defs>
          <polygon
            fill="url(#sdg)"
            points="0,30 30,26 60,28 90,18 120,21 150,12 180,15 210,6 240,10 250,4 250,40 0,40"
          />
          <polyline
            fill="none"
            stroke={T}
            strokeWidth="2.2"
            points="0,30 30,26 60,28 90,18 120,21 150,12 180,15 210,6 240,10 250,4"
          />
        </svg>
      </div>
      {rows.map(([sym, co, pr, chg, up]) => (
        <div
          key={sym}
          style={{
            ...panel,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: 11,
            marginBottom: 8,
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{sym}</div>
            <div style={{ fontSize: 10, color: "#5c7191" }}>{co}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: up ? T : BEAR }}>{pr}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: up ? T : BEAR }}>
              {up ? "▲" : "▼"} {chg}
            </div>
          </div>
        </div>
      ))}
    </>
  );
}

function SceneRealWealth() {
  return (
    <>
      <Head t="Real Wealth" pill="حقیقی دولت" />
      <div style={{ ...panel, padding: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#93a6c2" }}>
          Nominal vs. real, devaluation-adjusted
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            margin: "15px 0 6px",
            fontSize: 11,
            color: "#93a6c2",
          }}
        >
          <span>Nominal portfolio</span>
          <b style={{ color: "#fff", fontSize: 13 }}>PKR 4.20M</b>
        </div>
        <div
          style={{
            height: 16,
            borderRadius: 8,
            background: "rgba(255,255,255,.05)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: "100%",
              borderRadius: 8,
              background: "linear-gradient(90deg,#5a6474,#96a1b3)",
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            margin: "14px 0 6px",
            fontSize: 11,
            color: "#93a6c2",
          }}
        >
          <span>Real wealth</span>
          <b style={{ color: "#fff", fontSize: 13 }}>PKR 3.05M</b>
        </div>
        <div
          style={{
            height: 16,
            borderRadius: 8,
            background: "rgba(255,255,255,.05)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: "72%",
              borderRadius: 8,
              background: `linear-gradient(90deg,${T},#66f0d2)`,
            }}
          />
        </div>
        <div
          style={{
            marginTop: 15,
            padding: "11px 13px",
            borderRadius: 12,
            background: "rgba(255,91,106,.08)",
            border: "1px solid rgba(255,91,106,.22)",
            fontSize: 11,
            color: "#ffb0b8",
            lineHeight: 1.5,
          }}
        >
          ⚠ <b style={{ color: "#fff" }}>PKR 1.15M</b> of your “gains” is rupee illusion.
        </div>
      </div>
    </>
  );
}

function SceneSignal() {
  return (
    <>
      <Head t="Signals" pill="AI · live" />
      <div
        style={{
          background: `linear-gradient(150deg,rgba(0,212,170,.14),#0e1626 70%)`,
          border: "1px solid rgba(0,212,170,.28)",
          borderRadius: 16,
          padding: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>LUCK</div>
            <div style={{ fontSize: 10, color: "#5c7191" }}>Lucky Cement · Halal ✓</div>
          </div>
          <span
            style={{
              fontSize: 12,
              fontWeight: 800,
              color: "#022",
              background: T,
              padding: "7px 12px",
              borderRadius: 22,
              boxShadow: "0 0 20px rgba(0,212,170,.45)",
            }}
          >
            STRONG BUY
          </span>
        </div>
        <div style={{ ...panel, display: "flex", gap: 10, marginTop: 14, padding: 12 }}>
          <div
            style={{
              width: 28,
              height: 28,
              flex: "none",
              borderRadius: 8,
              display: "grid",
              placeItems: "center",
              background: "rgba(0,212,170,.15)",
              color: T,
              fontWeight: 800,
              fontSize: 11,
            }}
          >
            AI
          </div>
          <p style={{ fontSize: 11.5, lineHeight: 1.55, color: "#93a6c2" }}>
            Momentum turning up; real return beats inflation by{" "}
            <b style={{ color: "#66f0d2" }}>6.2%</b> this quarter.
          </p>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        {[
          ["Net worth", "3.05M"],
          ["Today", "+17.5K"],
          ["Halal", "92%"],
        ].map(([k, v]) => (
          <div key={k} style={{ ...panel, flex: 1, padding: 10 }}>
            <div
              style={{
                fontSize: 9,
                color: "#5c7191",
                textTransform: "uppercase",
                letterSpacing: 0.4,
              }}
            >
              {k}
            </div>
            <div style={{ fontSize: 14, fontWeight: 800, marginTop: 3, color: T }}>{v}</div>
          </div>
        ))}
      </div>
    </>
  );
}
