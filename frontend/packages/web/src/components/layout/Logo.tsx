import { Link } from "@tanstack/react-router";
import logo from "@/assets/logo.png";

export function Logo({ to = "/app" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2">
      <img src={logo} alt="NafaIQ" width={24} height={24} className="rounded-[6px]" />
      <span className="font-display text-base font-bold tracking-tight text-text-primary">
        Nafa<span className="text-primary">IQ</span>
      </span>
    </Link>
  );
}
