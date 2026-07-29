// NafaIQ logo mark — a monogram "N" drawn as a rising chart: two vertical
// strokes joined by an ascending/descending diagonal, with data-point nodes at
// the peaks. Pure vector (react-native-svg) so it stays crisp and themeable at
// any size — replaces the old raster bar-chart badge.
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from "react-native-svg";

export function NafaMark({ size = 34 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100" accessibilityLabel="NafaIQ">
      <Defs>
        <LinearGradient id="nafaTeal" x1="0" y1="1" x2="1" y2="0">
          <Stop offset="0" stopColor="#10B981" />
          <Stop offset="1" stopColor="#2DF2C4" />
        </LinearGradient>
      </Defs>
      {/* The "N": up (left) → diagonal → up (right). Rounded, bold. */}
      <Path
        d="M28 76 L28 28 L72 76 L72 28"
        stroke="url(#nafaTeal)"
        strokeWidth={13}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Chart data-point nodes at the peaks. */}
      <Circle cx={28} cy={28} r={7.5} fill="#2DF2C4" />
      <Circle cx={72} cy={28} r={7.5} fill="#2DF2C4" />
    </Svg>
  );
}
