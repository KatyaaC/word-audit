/**
 * Text normalisation + SHA-256 fingerprint for the Brand Passport.
 *
 * Must match the backend exactly (backend/app/services/passport.py):
 *
 *   fingerprint = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
 *
 * Only Windows line endings are normalised. Any other change, even a space,
 * gives a different fingerprint, so the Passport no longer verifies.
 */
export function canonicalize(text: string): string {
  return text.replace(/\r\n/g, "\n");
}

export async function sha256Hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function fingerprint(text: string): Promise<string> {
  return sha256Hex(canonicalize(text));
}
