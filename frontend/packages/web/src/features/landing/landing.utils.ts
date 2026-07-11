import { useEffect, useState } from "react";

export function usePsxOpen() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const check = () => {
      // PSX trades Mon–Fri, ~09:30–15:30 PKT (UTC+5)
      const now = new Date();
      const pkt = new Date(now.getTime() + (now.getTimezoneOffset() + 300) * 60000);
      const day = pkt.getDay();
      const mins = pkt.getHours() * 60 + pkt.getMinutes();
      setOpen(day >= 1 && day <= 5 && mins >= 570 && mins <= 930);
    };
    check();
    const id = setInterval(check, 60000);
    return () => clearInterval(id);
  }, []);
  return open;
}
