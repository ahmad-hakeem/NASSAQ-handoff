import { Loader2 } from "lucide-react";
import { cn } from "@/shared/models/lib/utils";
import { useTranslation } from "@/shared/contexts/ThemeContext";

const SPINNER_SIZES = {
  fullpage: "h-12 w-12",
  section: "h-8 w-8",
  inline: "h-4 w-4",
};

const CONTAINER_CLASSES = {
  fullpage: "min-h-[60vh] w-full flex flex-col items-center justify-center gap-4",
  section: "w-full flex flex-col items-center justify-center gap-3 py-12",
  inline: "inline-flex items-center gap-2",
};

/**
 * LoadingState — the platform-standard loading-before-data indicator.
 *
 * Variants:
 *   - "fullpage": page-level loading (large spinner, visible label by default)
 *   - "section":  table/tab/widget/panel loading (medium spinner, label optional)
 *   - "inline":   small inline spinner next to text
 *
 * All variants render role="status" with a localized aria-label so screen
 * readers announce the loading state even when no visible label is shown.
 * Extra props (e.g. data-testid) pass through to the root element.
 */
function LoadingState({ variant = "section", label, className, ...props }) {
  const { t } = useTranslation();
  const fallback = t("loading");
  const visibleLabel = label ?? (variant === "fullpage" ? fallback : null);

  return (
    <div
      role="status"
      aria-label={visibleLabel || fallback}
      className={cn(CONTAINER_CLASSES[variant] || CONTAINER_CLASSES.section, className)}
      {...props}
    >
      <Loader2
        aria-hidden="true"
        strokeWidth={1.5}
        className={cn(
          "animate-spin text-brand-turquoise shrink-0",
          SPINNER_SIZES[variant] || SPINNER_SIZES.section,
        )}
      />
      {visibleLabel ? (
        <p
          className={cn(
            "font-cairo text-slate-600 dark:text-slate-400",
            variant === "fullpage" ? "text-lg" : "text-sm",
          )}
        >
          {visibleLabel}
        </p>
      ) : null}
    </div>
  );
}

export { LoadingState };
export default LoadingState;
