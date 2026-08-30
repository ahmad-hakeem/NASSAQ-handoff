import React from "react";
import { useTheme } from "@/shared/contexts/ThemeContext";
import { Toaster as Sonner, toast } from "sonner";

const Toaster = ({ position, ...props }) => {
  const { theme = "light", isRTL } = useTheme();

  // In Arabic (RTL): toast appears on the Right side ("top-right")
  // In English (LTR): toast appears on the Left side ("top-left")
  const dynamicPosition = position || (isRTL ? "top-right" : "top-left");

  return (
    <Sonner
      theme={theme === "dark" ? "dark" : "light"}
      className="toaster group"
      position={dynamicPosition}
      dir={isRTL ? "rtl" : "ltr"}
      richColors={false}
      closeButton={true}
      duration={4000}
      offset="20px"
      toastOptions={{
        classNames: {
          toast:
            "group font-cairo toast group-[.toaster]:border group-[.toaster]:shadow-2xl group-[.toaster]:rounded-2xl group-[.toaster]:py-3.5 group-[.toaster]:px-4.5 group-[.toaster]:font-bold group-[.toaster]:text-sm group-[.toaster]:flex group-[.toaster]:items-center group-[.toaster]:gap-3 group-[.toaster]:transition-all group-[.toaster]:duration-300",
          title: "font-black text-sm text-white",
          description: "text-xs font-medium text-white/90 mt-0.5",
          icon: "[&_svg]:w-5 [&_svg]:h-5 shrink-0",
          success:
            "!bg-emerald-600 !text-white !border-emerald-500 shadow-emerald-900/30 [&_[data-icon]]:!text-white",
          error:
            "!bg-rose-600 !text-white !border-rose-500 shadow-rose-900/30 [&_[data-icon]]:!text-white",
          info:
            "!bg-[#1C3D74] !text-white !border-[#26539c] shadow-[#1C3D74]/30 [&_[data-icon]]:!text-[#00C5B2]",
          warning:
            "!bg-amber-500 !text-slate-950 !border-amber-400 shadow-amber-900/30 [&_[data-icon]]:!text-slate-950",
          actionButton:
            "!bg-white !text-slate-900 font-extrabold rounded-xl text-xs px-3.5 py-1.5 shadow-sm hover:!bg-slate-100",
          cancelButton:
            "!bg-black/20 !text-white font-bold rounded-xl text-xs px-3 py-1.5 hover:!bg-black/30",
          closeButton:
            "!bg-black/20 hover:!bg-black/40 !text-white !border-white/20 rounded-full shadow-xs transition-colors",
        },
      }}
      {...props}
    />
  );
};

export { Toaster, toast };
