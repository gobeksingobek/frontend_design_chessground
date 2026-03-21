import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

interface BoardWorkspaceProps {
  header?: ReactNode;
  board: ReactNode;
  main?: ReactNode;
  aside?: ReactNode;
  className?: string;
  boardWrapperClassName?: string;
  mainCardClassName?: string;
  asideCardClassName?: string;
}

export function BoardWorkspace({
  header,
  board,
  main,
  aside,
  className,
  boardWrapperClassName,
  mainCardClassName,
  asideCardClassName,
}: BoardWorkspaceProps) {
  return (
    <div className={cn("grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-start", className)}>
      <Card className={cn("gap-5", mainCardClassName)}>
        {header ? <div>{header}</div> : null}
        <div className={cn("w-full max-w-[900px] aspect-square mx-auto", boardWrapperClassName)}>
          {board}
        </div>
        {main ? <div>{main}</div> : null}
      </Card>
      {aside ? <Card className={cn("xl:sticky xl:top-24 xl:self-start", asideCardClassName)}>{aside}</Card> : null}
    </div>
  );
}
