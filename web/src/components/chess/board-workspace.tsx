import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { ResponsiveContextPanel } from "@/components/ui/responsive-context-panel";
import { cn } from "@/lib/cn";

interface BoardWorkspaceProps {
  header?: ReactNode;
  board: ReactNode;
  main?: ReactNode;
  aside?: ReactNode;
  asideLabel?: string;
  footer?: ReactNode;
  className?: string;
  heroClassName?: string;
  boardWrapperClassName?: string;
  mainCardClassName?: string;
  asideClassName?: string;
}

export function BoardWorkspace({
  header,
  board,
  main,
  aside,
  asideLabel = "Position context",
  footer,
  className,
  heroClassName,
  boardWrapperClassName,
  mainCardClassName,
  asideClassName,
}: BoardWorkspaceProps) {
  return (
    <div className={cn("grid gap-grid-gap xl:grid-cols-[minmax(0,1fr)_21rem] xl:items-start", className)}>
      <div className="grid min-w-0 gap-grid-gap">
        <Card variant="workspace" className={cn("gap-grid-gap overflow-hidden", heroClassName)}>
          {header ? <div>{header}</div> : null}
          <div className={cn("mx-auto aspect-square w-full max-w-[min(100%,calc(100vh-12rem))]", boardWrapperClassName)}>
            {board}
          </div>
          {main ? <Card variant="workspacePanel" className={cn("gap-grid-gap", mainCardClassName)}>{main}</Card> : null}
        </Card>
        {footer}
      </div>
      {aside ? <ResponsiveContextPanel label={asideLabel} className={asideClassName}>{aside}</ResponsiveContextPanel> : null}
    </div>
  );
}
