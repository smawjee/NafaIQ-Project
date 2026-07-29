import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { useAppDispatch } from "@/store/hooks";
import { resetDemoData } from "@/store/reset";

export function DemoBanner() {
  const { isDemo } = useDemo();
  const { t } = useLang();
  const dispatch = useAppDispatch();

  if (!isDemo) return null;

  return (
    <div className="border-b border-ai/20 bg-ai/10 px-4 py-2 text-center text-xs font-medium text-text-primary">
      {t("Demo Mode")} — {t("Your changes are not stored permanently.")}{" "}
      <Link
        to="/auth"
        className="inline-flex items-center gap-1 font-semibold text-ai underline underline-offset-2 hover:no-underline"
      >
        {t("Sign up")}
      </Link>{" "}
      {t("to keep your data permanently.")}{" "}
      <button
        type="button"
        onClick={() => {
          dispatch(resetDemoData());
          toast.success(t("Demo data reset"));
        }}
        className="inline-flex items-center gap-1 font-semibold text-ai underline underline-offset-2 hover:no-underline"
      >
        {t("Reset Demo Data")}
      </button>
    </div>
  );
}
