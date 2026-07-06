import { clsx, type ClassValue } from "clsx";
import Image from "next/image";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("rounded-control border border-line bg-surface shadow-soft", className)} {...props} />;
}

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("inline-flex h-6 items-center rounded-full border border-line bg-panel px-2 text-xs text-muted", className)}
      {...props}
    />
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-control px-4 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-55",
        variant === "primary" && "bg-brand text-white shadow-button hover:bg-brandDeep",
        variant === "secondary" && "border border-line bg-surface text-ink hover:bg-panel",
        variant === "ghost" && "text-muted hover:bg-panel hover:text-ink",
        className
      )}
      {...props}
    />
  );
}

type AppButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
};

export function AppButton({ className, variant = "primary", size = "md", ...props }: AppButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control text-sm font-semibold transition duration-200 disabled:cursor-not-allowed disabled:opacity-55",
        size === "md" && "h-11 px-4",
        size === "lg" && "h-12 px-5",
        variant === "primary" && "bg-brand text-white shadow-button hover:-translate-y-0.5 hover:bg-brandDeep",
        variant === "secondary" && "border border-line bg-surface text-ink shadow-soft hover:-translate-y-0.5 hover:border-brand/30 hover:bg-brandMist",
        variant === "ghost" && "text-muted hover:bg-brandSoft hover:text-ink",
        className
      )}
      {...props}
    />
  );
}

type AppInputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  helper?: string;
  error?: string;
  containerClassName?: string;
};

export function AppInput({ label, helper, error, className, containerClassName, ...props }: AppInputProps) {
  return (
    <label className={cn("grid gap-2 text-sm", containerClassName)}>
      {label ? <span className="font-medium text-ink">{label}</span> : null}
      <input
        className={cn(
          "h-12 rounded-control border border-line bg-surface px-4 text-sm text-ink shadow-[0_1px_0_rgba(15,23,42,0.02)] transition placeholder:text-[#98a2b3]",
          "focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10",
          error && "border-accent focus:border-accent focus:ring-accent/10",
          className
        )}
        {...props}
      />
      {error ? <span className="text-xs text-accent">{error}</span> : helper ? <span className="text-xs text-muted">{helper}</span> : null}
    </label>
  );
}

export function AppCard({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={cn("rounded-app border border-line/80 bg-surface/95 shadow-card backdrop-blur", className)}
      {...props}
    />
  );
}

export function PageShell({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <main
      className={cn("mx-auto min-h-[calc(100vh-3.5rem)] w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8", className)}
      {...props}
    />
  );
}

type BrandLogoProps = {
  variant?: "wordmark" | "mark";
  className?: string;
  imageClassName?: string;
  priority?: boolean;
};

export function BrandLogo({ variant = "wordmark", className, imageClassName, priority }: BrandLogoProps) {
  const isMark = variant === "mark";
  return (
    <span className={cn("relative block overflow-hidden", isMark ? "aspect-square" : "aspect-[3/1]", className)}>
      <Image
        src={isMark ? "/brand/logo-mark.png" : "/brand/logo-wordmark.png"}
        alt="iweioo"
        width={isMark ? 240 : 420}
        height={isMark ? 240 : 140}
        priority={priority}
        className={cn("h-full w-full object-contain", imageClassName)}
      />
    </span>
  );
}
