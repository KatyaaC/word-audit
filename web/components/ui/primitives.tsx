/**
 * shadcn/ui-style primitives (same API shape as `npx shadcn add button card badge input textarea label`).
 * Kept in one file so the project builds offline. Swap for the generated shadcn files any time.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// ---------- Button ----------

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-emerald-800 text-white hover:bg-emerald-700",
        secondary: "bg-stone-200 text-stone-900 hover:bg-stone-300",
        outline: "border border-stone-300 bg-white text-stone-900 hover:bg-stone-50",
        ghost: "text-stone-700 hover:bg-stone-100",
        destructive: "bg-red-700 text-white hover:bg-red-600",
      },
      size: { default: "h-9 px-4", sm: "h-8 px-3 text-xs", lg: "h-10 px-6", icon: "h-8 w-8" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";

// ---------- Card ----------

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-stone-200 bg-white shadow-sm", className)} {...props} />;
}
export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-5 pb-3", className)} {...props} />;
}
export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold leading-tight", className)} {...props} />;
}
export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-stone-500", className)} {...props} />;
}
export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

// ---------- Badge ----------

export const badgeVariants = cva("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      default: "border-transparent bg-stone-800 text-white",
      outline: "border-stone-300 text-stone-700",
      high: "border-red-200 bg-red-50 text-red-800",
      medium: "border-amber-200 bg-amber-50 text-amber-800",
      low: "border-blue-200 bg-blue-50 text-blue-800",
      success: "border-emerald-200 bg-emerald-50 text-emerald-800",
      warning: "border-orange-200 bg-orange-50 text-orange-800",
      muted: "border-stone-200 bg-stone-100 text-stone-700",
      violet: "border-violet-200 bg-violet-50 text-violet-800",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

// ---------- Form controls ----------

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-md border border-stone-300 bg-white px-3 text-sm placeholder:text-stone-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "min-h-20 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm placeholder:text-stone-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium text-stone-700", className)} {...props} />;
}

export const NativeSelect = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "h-9 rounded-md border border-stone-300 bg-white px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600",
        className,
      )}
      {...props}
    />
  ),
);
NativeSelect.displayName = "NativeSelect";

// ---------- Tabs (controlled) ----------

export function Tabs<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: React.ReactNode }[];
}) {
  return (
    <div role="tablist" className="flex gap-1 rounded-lg bg-stone-100 p-1">
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            value === it.value ? "bg-white shadow-sm" : "text-stone-600 hover:text-stone-900",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{message}</p>;
}
