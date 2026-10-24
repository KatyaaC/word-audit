import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function shortHash(hex: string, n = 12): string {
  return hex.length > n ? `${hex.slice(0, n)}…` : hex;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
