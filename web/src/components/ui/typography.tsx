import { ElementType, ReactNode } from "react";

import { cn } from "@/lib/cn";

type TypographyProps<T extends ElementType> = {
  as?: T;
  children: ReactNode;
  className?: string;
};

function Typography<T extends ElementType = "p">({
  as,
  children,
  className,
}: TypographyProps<T>) {
  const Component = as ?? "p";

  return <Component className={className}>{children}</Component>;
}

export function PageTitle<T extends ElementType = "h1">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "h1"} className={cn("text-display font-semibold tracking-tight text-foreground", props.className)}>{props.children}</Typography>;
}

export function SectionTitle<T extends ElementType = "h2">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "h2"} className={cn("text-page-title font-semibold tracking-tight text-foreground", props.className)}>{props.children}</Typography>;
}

export function CardTitle<T extends ElementType = "h3">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "h3"} className={cn("text-card-title font-semibold text-foreground", props.className)}>{props.children}</Typography>;
}

export function BodyText<T extends ElementType = "p">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "p"} className={cn("text-body leading-7 text-foreground", props.className)}>{props.children}</Typography>;
}

export function FieldLabel<T extends ElementType = "span">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "span"} className={cn("text-label font-medium text-muted-foreground", props.className)}>{props.children}</Typography>;
}

export function MutedText<T extends ElementType = "p">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "p"} className={cn("text-body leading-7 text-muted-foreground", props.className)}>{props.children}</Typography>;
}

export function CaptionText<T extends ElementType = "small">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "small"} className={cn("text-caption font-medium uppercase tracking-[0.14em] text-muted-foreground/85", props.className)}>{props.children}</Typography>;
}

export function MonoText<T extends ElementType = "code">(props: TypographyProps<T>) {
  return <Typography as={props.as ?? "code"} className={cn("font-mono text-mono text-muted-foreground", props.className)}>{props.children}</Typography>;
}
