import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

export function StatCard({ label, value, detail, action, className }: { label: string; value: ReactNode; detail?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-3", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-2">
          <CaptionText>{label}</CaptionText>
          <CardTitle className="text-2xl">{value}</CardTitle>
        </div>
        {action}
      </div>
      {detail ? <MutedText className="leading-6">{detail}</MutedText> : null}
    </Card>
  );
}
