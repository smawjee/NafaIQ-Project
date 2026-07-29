// Decorative premium "stock" area chart for the intro's lower area — a smooth
// upward-trending line with a glowing teal gradient fill and a pulsing end node.
// Pure vector; the parent animates it (fades/slides down to dissolve on exit).
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from "react-native-svg";

// A smooth, confidently-rising trend traced with cubic beziers.
const LINE = "M0 80 C 26 76 44 60 70 63 S 112 40 140 45 S 182 20 210 28 S 258 8 300 14";
const AREA = `${LINE} L300 100 L0 100 Z`;

export function LiquidStockGraph({ width, height = 96 }: { width: number; height?: number }) {
  return (
    <Svg width={width} height={height} viewBox="0 0 300 100" preserveAspectRatio="none">
      <Defs>
        <LinearGradient id="lsgArea" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor="#00D4AA" stopOpacity={0.3} />
          <Stop offset="0.6" stopColor="#00D4AA" stopOpacity={0.08} />
          <Stop offset="1" stopColor="#00D4AA" stopOpacity={0} />
        </LinearGradient>
        <LinearGradient id="lsgLine" x1="0" y1="0" x2="1" y2="0">
          <Stop offset="0" stopColor="#10B981" />
          <Stop offset="1" stopColor="#2DF2C4" />
        </LinearGradient>
      </Defs>
      <Path d={AREA} fill="url(#lsgArea)" />
      <Path
        d={LINE}
        stroke="url(#lsgLine)"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        vectorEffect="non-scaling-stroke"
      />
      <Circle cx={300} cy={14} r={4} fill="#2DF2C4" />
    </Svg>
  );
}
