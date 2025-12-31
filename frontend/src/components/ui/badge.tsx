import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border border-ink-200 bg-white/80 px-3 py-1 text-xs font-semibold tracking-wide text-ink-700",
  {
    variants: {
      variant: {
        default: "",
        accent: "border-teal-200 bg-teal-100 text-teal-900",
        warn: "border-orange-200 bg-orange-100 text-orange-900"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
