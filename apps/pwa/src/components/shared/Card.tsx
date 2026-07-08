import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { motion, useReducedMotion, SPRING_UI } from "@/components/shared/animations";

export function Card({
  className,
  children,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div
      className={cn("glass-card rounded-[14px] p-6", hover && "glass-card-hover", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  subColor = "text-text-secondary",
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  subColor?: string;
}) {
  const { t } = useLang();
  const reduce = useReducedMotion();
  const content = (
    <>
      <div className="text-xs font-medium text-text-secondary">{t(label)}</div>
      <div className="mt-2 font-mono text-xl font-bold tabular-nums text-text-primary md:text-2xl">
        {value}
      </div>
      {sub && <div className={cn("mt-1 font-mono text-xs tabular-nums", subColor)}>{sub}</div>}
    </>
  );
  if (reduce) return <Card>{content}</Card>;
  return (
    <motion.div
      className="glass-card glass-card-hover rounded-[14px] p-6"
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.4 }}
      whileHover={{ y: -3 }}
      transition={SPRING_UI}
    >
      {content}
    </motion.div>
  );
}

