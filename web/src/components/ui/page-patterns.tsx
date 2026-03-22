import { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeader } from "@/components/ui/section-header";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";

export { EmptyState };

export function KpiSummary({ children, className }: { children: ReactNode; className?: string }) {
  return <Card className={cn("gap-grid-gap", className)}>{children}</Card>;
}

export function FilterPanel({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-control-gap border-border/80 bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <MutedText>{description}</MutedText> : null}
      {children}
    </Card>
  );
}

export function DataTableSection({ title, description, actions, children, className }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-grid-gap", className)}>
      {title ? <SectionHeader title={title} description={description} actions={actions} /> : description || actions ? <div className="grid gap-sm">{description ? <MutedText>{description}</MutedText> : null}{actions ? <div className="flex flex-wrap items-center gap-sm">{actions}</div> : null}</div> : null}
      {children}
    </div>
  );
}

export function DetailPane({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-grid-gap bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <MutedText>{description}</MutedText> : null}
      {children}
    </Card>
  );
}

export function HeroWorkspaceSection({
  title,
  description,
  actions,
  hero,
  support,
  children,
  className,
  heroClassName,
  contentClassName,
  supportClassName,
}: {
  title?: string;
  description?: ReactNode;
  actions?: ReactNode;
  hero?: ReactNode;
  support?: ReactNode;
  children: ReactNode;
  className?: string;
  heroClassName?: string;
  contentClassName?: string;
  supportClassName?: string;
}) {
  return (
    <section className={cn("grid gap-grid-gap", className)}>
      {title ? <SectionHeader title={title} description={description} actions={actions} /> : description || actions ? <div className="grid gap-sm">{description ? <MutedText as="div">{description}</MutedText> : null}{actions ? <div className="flex flex-wrap items-center gap-sm">{actions}</div> : null}</div> : null}
      <div className={cn("grid gap-grid-gap xl:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.9fr)] xl:items-start", contentClassName)}>
        <div className="grid gap-grid-gap">
          {hero ? <Card variant="workspace" className={cn("gap-grid-gap overflow-hidden", heroClassName)}>{hero}</Card> : null}
          {children}
        </div>
        {support ? <SupportRail className={supportClassName}>{support}</SupportRail> : null}
      </div>
    </section>
  );
}

export function SupportRail({ children, className }: { children: ReactNode; className?: string }) {
  return <aside className={cn("grid gap-lg lg:sticky lg:top-6 lg:self-start", className)}>{children}</aside>;
}

export function UtilityPanelStack({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid gap-md", className)}>{children}</div>;
}

export function UtilityPanel({
  title,
  description,
  eyebrow,
  actions,
  children,
  className,
  contentClassName,
}: {
  title?: string;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <Card variant="utility" className={cn("gap-md rounded-xl", className)}>
      {title || description || eyebrow || actions ? (
        <div className="grid gap-2">
          {eyebrow ? <CaptionText className="text-[0.68rem] tracking-[0.16em] text-muted-foreground/75">{eyebrow}</CaptionText> : null}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="grid gap-1.5">
              {title ? <CardTitle className="text-sm font-semibold text-foreground/95">{title}</CardTitle> : null}
              {description ? <MutedText as="div" className="text-sm leading-6">{description}</MutedText> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </div>
      ) : null}
      <div className={cn("grid gap-sm", contentClassName)}>{children}</div>
    </Card>
  );
}

export function UtilityPanelGroup({
  title,
  description,
  children,
  className,
}: {
  title?: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("grid gap-2.5", className)}>
      {title || description ? (
        <div className="grid gap-1">
          {title ? <CardTitle className="text-sm text-foreground/90">{title}</CardTitle> : null}
          {description ? <MutedText as="div" className="text-sm leading-6">{description}</MutedText> : null}
        </div>
      ) : null}
      <div className="grid gap-sm">{children}</div>
    </section>
  );
}

export function SecondaryModuleStack({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
}: {
  title?: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <Card variant="soft" className={cn("gap-grid-gap", className)}>
      {title ? <SectionHeader title={title} description={description} actions={actions} /> : description || actions ? <div className="grid gap-sm">{description ? <MutedText as="div">{description}</MutedText> : null}{actions ? <div className="flex flex-wrap items-center gap-sm">{actions}</div> : null}</div> : null}
      <div className={cn("grid gap-control-gap", contentClassName)}>{children}</div>
    </Card>
  );
}

export function DenseControlRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-sm", className)}>{children}</div>;
}

export function InsightCallout({ title, description }: { title: string; description: string }) {
  return <div className="rounded-xl border border-border/70 bg-card px-4 py-4"><CardTitle className="text-base">{title}</CardTitle><MutedText className="mt-2">{description}</MutedText></div>;
}
