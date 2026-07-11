import logo from "@/assets/logo.png";

export function LogoIcon({ className }: { className?: string }) {
  return <img src={logo} alt="NafaIQ" width={36} height={36} className={className} />;
}
