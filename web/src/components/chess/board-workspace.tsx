import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { SupportRail, WorkspaceLayout } from "@/components/ui/page-patterns";
import { cn } from "@/lib/cn";

interface BoardWorkspaceProps {
  header?: ReactNode;
  board: ReactNode;
  main?: ReactNode;
  aside?: ReactNode;
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
  footer,
  className,
  heroClassName,
  boardWrapperClassName,
  mainCardClassName,
  asideClassName,
}: BoardWorkspaceProps) {
  return (
    <WorkspaceLayout
      className={className}
      heroClassName={heroClassName}
      support={aside ? <SupportRail className={asideClassName}>{aside}</SupportRail> : undefined}
      hero={(
        <div className="grid gap-grid-gap">
          {header ? <div>{header}</div> : null}
          <div className={cn("mx-auto aspect-square w-full max-w-[900px]", boardWrapperClassName)}>
            {board}
          </div>
          {main ? <Card variant="workspacePanel" className={cn("gap-grid-gap", mainCardClassName)}>{main}</Card> : null}
        </div>
      )}
    >
      {footer}
    </WorkspaceLayout>
  );
}
