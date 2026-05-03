import { useTheme } from "next-themes"
import { Toaster as Sonner, toast } from "sonner"

const BRAND_TURQUOISE = "#14B8A6"

const Toaster = ({
  ...props
}) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      position="top-center"
      style={{
        top: "50%",
        left: "50%",
        right: "auto",
        bottom: "auto",
        transform: "translate(-50%, -50%)",
      }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "flex items-center gap-3 font-medium text-white",
          title: "text-white",
          description: "text-white/90",
          icon: "text-white [&_svg]:text-white [&_svg]:fill-white/0",
          success: "text-white",
          error: "text-white",
          info: "text-white",
          warning: "text-white",
        },
        style: {
          background: BRAND_TURQUOISE,
          color: "#FFFFFF",
          border: "none",
          borderRadius: "8px",
          padding: "16px 24px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
          width: "auto",
          minWidth: "260px",
        },
      }}
      {...props} />
  );
}

export { Toaster, toast }
