// The premium liquid-glass auth flow. On first open it plays a ~2.8s intro — the
// slowly-rotating glass star + centred logo — then the star "explodes away", the
// logo flies to the top, and the sign-in form fades in. Sign-in ⇄ sign-up toggle
// in place. Keyboard-aware (fields lift above the keyboard). Honors reduce-motion
// (skips straight to the form). Always dark (public screen).
import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Alert,
  ImageBackground,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import Animated, {
  Easing,
  interpolate,
  runOnJS,
  useAnimatedKeyboard,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Field, GlassButton, PasswordField, PrimaryButton } from "@/components/auth/auth-fields";
import { ForgotPasswordCard } from "@/components/auth/ForgotPasswordCard";
import { GlassCard } from "@/components/glass/GlassCard";
import { LiquidGlassStar } from "@/components/glass/LiquidGlassStar";
import { LiquidStockGraph } from "@/components/glass/LiquidStockGraph";
import { Logo } from "@/components/Logo";
import { Text } from "@/components/ui";
import { colors, fonts, radii } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { usePlatformFlags } from "@/hooks/queries/use-platform-flags";
import { Activity, ShieldCheck, Sparkles } from "@/lib/icons";

const bgSource = require("../../../assets/generated/landing-bg.webp");
const LOGO_H = 64;
const INTRO_HOLD = 2800;

type Mode = "signin" | "signup" | "forgot";

export function AuthExperience({ intro = false }: { intro?: boolean }) {
  const { signInWithPassword, signUpWithPassword, signInWithGoogle } = useAuth();
  const { registrationEnabled, maintenanceMode } = usePlatformFlags();
  const { width: winW, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const keyboard = useAnimatedKeyboard();

  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(!intro);
  // Screen-Y of the lowest interactive row — used to lift the form by only the
  // amount the keyboard actually overlaps (avoids over-lifting).
  const [anchorY, setAnchorY] = useState(0);

  const enter = useSharedValue(intro ? 0 : 1); // entrance pop
  const p = useSharedValue(intro ? 0 : 1); // 0 = intro, 1 = auth
  const spin = useSharedValue(0); // slow ambient star rotation
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    let cancelled = false;
    const scheduled = timers.current;
    AccessibilityInfo.isReduceMotionEnabled().then((reduced) => {
      if (cancelled) return;
      if (!intro || reduced) {
        enter.value = 1;
        p.value = 1;
        setShowForm(true);
        return;
      }
      // 1) pop the hero in, 2) hold ~2.8s, 3) explode + fly logo up + reveal form.
      enter.value = withTiming(1, { duration: 780, easing: Easing.out(Easing.cubic) });
      spin.value = withRepeat(withTiming(1, { duration: 26000, easing: Easing.linear }), -1, false);
      scheduled.push(
        setTimeout(() => {
          p.value = withTiming(1, { duration: 1350, easing: Easing.inOut(Easing.cubic) }, (done) => {
            "worklet";
            if (done) runOnJS(setShowForm)(true);
          });
        }, INTRO_HOLD),
      );
    });
    return () => {
      cancelled = true;
      scheduled.forEach(clearTimeout);
    };
  }, [intro, enter, p, spin]);

  // Geometry: logo travels from screen centre to just below the top inset.
  const centerTop = height / 2 - LOGO_H / 2;
  const targetTop = insets.top + 10;
  const deltaY = targetTop - centerTop;

  const scrimStyle = useAnimatedStyle(() => ({
    // Heavier during the intro (makes the glass pop); lifts for the form so the
    // bolder contour background stays visible.
    opacity: interpolate(p.value, [0, 1], [0.42, 0.14]),
  }));

  const heroStyle = useAnimatedStyle(() => ({
    opacity: enter.value,
    transform: [
      { rotate: `${interpolate(spin.value, [0, 1], [0, 360])}deg` },
      { scale: interpolate(enter.value, [0, 1], [0.82, 1]) },
    ],
  }));

  const logoStyle = useAnimatedStyle(() => ({
    opacity: enter.value,
    top: centerTop,
    transform: [
      { translateY: interpolate(p.value, [0, 1], [0, deltaY]) },
      { scale: interpolate(enter.value, [0, 1], [0.82, 1]) * interpolate(p.value, [0, 1], [1, 0.82]) },
    ],
  }));

  const taglineStyle = useAnimatedStyle(() => ({
    opacity: interpolate(p.value, [0, 0.4], [enter.value, 0]),
    transform: [{ translateY: interpolate(p.value, [0, 1], [0, -24]) }],
  }));

  const formStyle = useAnimatedStyle(() => {
    const base = interpolate(p.value, [0.5, 1], [28, 0]);
    const kb = keyboard.height.value;
    // Only lift by however much the keyboard covers the lowest interactive row.
    const overlap = kb > 0 && anchorY > 0 ? Math.max(0, anchorY + 20 - (height - kb)) : 0;
    return {
      opacity: interpolate(p.value, [0.5, 1], [0, 1]),
      transform: [{ translateY: base - overlap }],
    };
  });

  const graphStyle = useAnimatedStyle(() => ({
    opacity: interpolate(p.value, [0, 0.5], [enter.value, 0]),
    transform: [
      { translateY: interpolate(enter.value, [0, 1], [24, 0]) + interpolate(p.value, [0, 1], [0, 96]) },
    ],
  }));

  const footerStyle = useAnimatedStyle(() => ({
    // Fades in with the form; tucks away when the keyboard is up.
    opacity:
      interpolate(p.value, [0.6, 1], [0, 1]) *
      interpolate(keyboard.height.value, [0, 90], [1, 0], "clamp"),
  }));

  async function submit() {
    if (busy) return;
    if (maintenanceMode) return Alert.alert("NafaIQ is under maintenance", "Please try again shortly.");
    setBusy(true);
    try {
      if (mode === "signup") {
        if (!registrationEnabled) return Alert.alert("Registration is currently closed");
        if (name.trim().length < 2) return Alert.alert("Please enter your name");
        const passwordValid =
          password.length >= 8 && /[A-Z]/.test(password) && /\d/.test(password) && /[^A-Za-z0-9]/.test(password);
        if (!passwordValid) return Alert.alert("Choose a stronger password", "Use 8+ characters with an uppercase letter, number, and special character.");
        const { error, needsConfirmation } = await signUpWithPassword(email.trim(), password, name.trim());
        if (error) return Alert.alert("Sign up failed", error);
        if (needsConfirmation) {
          setMode("signin");
          Alert.alert("Check your email", "Confirm your email address, then return here to sign in.");
        } else {
          Alert.alert("Account created — welcome to NafaIQ!");
        }
      } else {
        const { error } = await signInWithPassword(email.trim(), password);
        if (error) return Alert.alert("Sign in failed", error);
      }
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    if (busy) return;
    if (maintenanceMode) return Alert.alert("NafaIQ is under maintenance", "Please try again shortly.");
    setBusy(true);
    const { error } = await signInWithGoogle();
    if (error) Alert.alert("Google sign-in failed", error);
    setBusy(false);
  }

  const isSignup = mode === "signup";
  const isForgot = mode === "forgot";

  return (
    <View style={styles.root}>
      <ImageBackground source={bgSource} style={StyleSheet.absoluteFill} resizeMode="cover">
        <Animated.View style={[styles.scrim, scrimStyle]} pointerEvents="none" />
        {/* Soft emerald glow anchored to the bottom — fills the lower space. */}
        <LinearGradient
          colors={["transparent", "rgba(0,212,170,0.05)", "rgba(0,212,170,0.12)"]}
          style={styles.bottomGlow}
          pointerEvents="none"
        />

        {/* Hero glass star (intro) — behind everything, slowly rotating. */}
        <Animated.View style={[styles.heroWrap, heroStyle]} pointerEvents="none">
          <LiquidGlassStar size={Math.min(height * 0.28, 240)} progress={p} />
        </Animated.View>

        {/* Logo card — centre in intro, flies to top for the form. */}
        <Animated.View style={[styles.logoWrap, logoStyle]} pointerEvents="none">
          <GlassCard radius={20} intensity={30} sheen={0.16} style={styles.logoCard}>
            <Logo size={34} />
          </GlassCard>
        </Animated.View>

        {/* Intro tagline. */}
        <Animated.View style={[styles.taglineWrap, taglineStyle]} pointerEvents="none">
          <Text style={styles.tagline1}>PSX. Finance. AI.</Text>
          <Text style={styles.tagline2}>One Terminal</Text>
        </Animated.View>

        {/* Intro stock graph — fills the lower space; dissolves downward on exit. */}
        <Animated.View style={[styles.graphWrap, graphStyle]} pointerEvents="none">
          <LiquidStockGraph width={winW - 44} />
        </Animated.View>

        {/* Auth form — fades in as the intro resolves; lifts with the keyboard. */}
        <Animated.View
          style={[styles.formWrap, { top: insets.top + LOGO_H + 18 }, formStyle]}
          pointerEvents={showForm ? "auto" : "none"}
        >
          <ScrollView
            contentContainerStyle={[styles.formContent, { paddingBottom: insets.bottom + 28 }]}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <Text style={styles.title}>
              {isForgot ? "Reset password" : isSignup ? "Create account" : "Welcome back"}
            </Text>
            <Text variant="secondary" style={styles.subtitle}>
              {isForgot
                ? "We'll get you back into your account."
                : isSignup
                  ? "Start your journey with intelligent PSX insights."
                  : "Sign in to your NafaIQ terminal."}
            </Text>

            {maintenanceMode ? (
              <View style={styles.notice}>
                <Text style={styles.noticeTitle}>Scheduled maintenance</Text>
                <Text variant="secondary" style={{ fontSize: 12 }}>The terminal is temporarily unavailable. Your data remains secure.</Text>
              </View>
            ) : null}

            {isSignup && !registrationEnabled ? (
              <View style={styles.notice}>
                <Text style={styles.noticeTitle}>Registration is currently closed</Text>
                <Text variant="secondary" style={{ fontSize: 12 }}>Existing members can still sign in.</Text>
              </View>
            ) : null}

            <GlassCard radius={radii.card} intensity={26} style={styles.card}>
              <View style={styles.cardInner}>
                {isForgot ? (
                  <ForgotPasswordCard onBackToSignIn={() => setMode("signin")} />
                ) : (
                  <>
                    <GlassButton
                      label="Continue with Google"
                      onPress={google}
                      disabled={busy || maintenanceMode}
                    />

                    <View style={styles.divider}>
                      <View style={styles.line} />
                      <Text variant="muted">or</Text>
                      <View style={styles.line} />
                    </View>

                    {isSignup && (
                      <Field label="Name" value={name} onChangeText={setName} placeholder="Ahmed Khan" autoCapitalize="words" />
                    )}
                    <Field
                      label="Email"
                      value={email}
                      onChangeText={setEmail}
                      placeholder="you@example.com"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      autoComplete="email"
                      inputMode="email"
                    />
                    <PasswordField value={password} onChangeText={setPassword} />

                    {isSignup ? <PasswordChecklist password={password} /> : null}

                    {!isSignup && (
                      <Pressable
                        onPress={() => setMode("forgot")}
                        hitSlop={12}
                        accessibilityRole="button"
                        accessibilityLabel="Forgot password"
                        style={styles.forgotRow}
                      >
                        <Text style={styles.switchLink}>Forgot password?</Text>
                      </Pressable>
                    )}

                    <PrimaryButton
                      label={isSignup ? "Create account" : "Sign in"}
                      onPress={submit}
                      loading={busy}
                      disabled={maintenanceMode || (isSignup && !registrationEnabled)}
                    />
                  </>
                )}
              </View>
            </GlassCard>

            {!isForgot && (
              <View
                style={styles.switchRow}
                onLayout={(e) => {
                  const { y, height: h } = e.nativeEvent.layout;
                  setAnchorY(insets.top + LOGO_H + 18 + y + h);
                }}
              >
                <Text variant="secondary">
                  {isSignup ? "Already have an account?" : "Don't have an account?"}
                </Text>
                {isSignup || registrationEnabled ? (
                  <Text
                    onPress={() => setMode(isSignup ? "signin" : "signup")}
                    style={styles.switchLink}
                    accessibilityRole="button"
                  >
                    {isSignup ? "Sign in" : "Sign up"}
                  </Text>
                ) : null}
              </View>
            )}
          </ScrollView>
        </Animated.View>

        {/* Premium trust footer — fills the lower area, hides with the keyboard. */}
        <Animated.View
          style={[styles.footer, { bottom: insets.bottom + 16 }, footerStyle]}
          pointerEvents="none"
        >
          <TrustItem icon={ShieldCheck} label="Bank-grade secure" />
          <View style={styles.footerDot} />
          <TrustItem icon={Activity} label="Real-time PSX" />
          <View style={styles.footerDot} />
          <TrustItem icon={Sparkles} label="AI insights" />
        </Animated.View>
      </ImageBackground>
    </View>
  );
}

function PasswordChecklist({ password }: { password: string }) {
  const checks = [
    [password.length >= 8, "8 or more characters"],
    [/[A-Z]/.test(password), "Uppercase letter"],
    [/\d/.test(password), "Number"],
    [/[^A-Za-z0-9]/.test(password), "Special character"],
  ] as const;
  return (
    <View style={styles.checks}>
      {checks.map(([ok, label]) => (
        <Text key={label} style={{ color: ok ? colors.primary : colors.textMuted, fontSize: 11 }}>
          {ok ? "✓" : "○"} {label}
        </Text>
      ))}
    </View>
  );
}
function TrustItem({ icon: Icon, label }: { icon: typeof ShieldCheck; label: string }) {
  return (
    <View style={styles.trustItem}>
      <Icon color={colors.textMuted} size={13} />
      <Text style={styles.trustText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.background },
  bottomGlow: { position: "absolute", left: 0, right: 0, bottom: 0, height: "34%" },

  heroWrap: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center" },

  logoWrap: { position: "absolute", left: 0, right: 0, alignItems: "center" },
  logoCard: { paddingHorizontal: 18, height: LOGO_H, alignItems: "center", justifyContent: "center", flexDirection: "row" },

  graphWrap: { position: "absolute", left: 22, right: 22, bottom: "10%", alignItems: "center" },
  taglineWrap: { position: "absolute", left: 0, right: 0, bottom: "26%", alignItems: "center" },
  tagline1: { fontSize: 27, fontWeight: "700", color: colors.textPrimary, letterSpacing: 0.5, fontFamily: fonts.heading },
  tagline2: { fontSize: 31, fontWeight: "800", color: colors.primary, letterSpacing: 0.5, marginTop: 2, fontFamily: fonts.heading },

  formWrap: { position: "absolute", left: 0, right: 0, bottom: 0 },
  formContent: { paddingHorizontal: 22, paddingTop: 24, gap: 6 },
  title: { fontSize: 30, fontWeight: "800", color: colors.textPrimary, letterSpacing: -0.5, fontFamily: fonts.heading },
  subtitle: { marginTop: 2, marginBottom: 18 },
  notice: { borderWidth: 1, borderColor: colors.warning + "55", backgroundColor: colors.warning + "12", borderRadius: 12, padding: 12, gap: 3, marginBottom: 8 },
  noticeTitle: { color: colors.warning, fontFamily: fonts.headingMedium, fontWeight: "700", fontSize: 13 },

  card: {},
  cardInner: { padding: 18, gap: 14 },

  divider: { flexDirection: "row", alignItems: "center", gap: 10 },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: "rgba(255,255,255,0.14)" },

  fieldGlass: {},
  input: {
    minHeight: 50,
    paddingHorizontal: 14,
    color: colors.textPrimary,
    fontSize: 15,
    fontFamily: fonts.sans,
  },
  pwRow: { flexDirection: "row", alignItems: "center" },
  pwToggle: { paddingHorizontal: 14, height: 50, alignItems: "center", justifyContent: "center" },
  checks: { flexDirection: "row", flexWrap: "wrap", columnGap: 12, rowGap: 5 },

  primaryBtn: {
    minHeight: 52,
    borderRadius: radii.btn,
    overflow: "hidden",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 2,
  },
  primaryText: { color: colors.primaryForeground, fontWeight: "800", fontSize: 16, fontFamily: fonts.sans },

  glassBtn: { minHeight: 52, alignItems: "center", justifyContent: "center" },
  glassBtnText: { color: colors.textPrimary, fontWeight: "600", fontSize: 15, fontFamily: fonts.sans },

  switchRow: { flexDirection: "row", justifyContent: "center", gap: 6, marginTop: 18 },
  switchLink: { color: colors.primary, fontWeight: "700" },
  // 44pt tall so the tap target clears the accessibility minimum.
  forgotRow: { minHeight: 44, alignItems: "flex-end", justifyContent: "center" },

  footer: { position: "absolute", left: 0, right: 0, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  footerDot: { width: 3, height: 3, borderRadius: 2, backgroundColor: colors.textMuted, opacity: 0.6 },
  trustItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  trustText: { fontSize: 11, color: colors.textMuted, fontWeight: "600", fontFamily: fonts.sans },
});
