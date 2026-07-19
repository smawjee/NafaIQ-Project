import { Line, LineChart, ResponsiveContainer } from "recharts";
import { useTheme } from "@/hooks/use-theme";

/** Remap neon dark-theme hexes to deeper, desaturated light-theme equivalents. */
const LIGHT_SPARK: Record<string, string> = {
  "#00d4aa": "#0d9488",
  "#e5484d": "#c4615a",
};

export function Sparkline({ data, color }: { data: number[]; color: string }) {
  const { theme } = useTheme();
  const stroke = theme === "light" ? (LIGHT_SPARK[color.toLowerCase()] ?? color) : color;
  const d = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={d} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
        <Line type="monotone" dataKey="v" stroke={stroke} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
