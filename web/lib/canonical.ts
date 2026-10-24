/**
 * Canonical text + SHA-256 fingerprint for the Brand Passport.
 *
 * The backend MUST canonicalise the same way, or verification will fail on
 * harmless whitespace. Python equivalent (for Sudiksha):
 *
 *   def canonicalize(text: str) -> str:
 *       t = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
 *       lines = [re.sub(r"[ \t]+", " ", line).strip() for line in t.split("\n")]
 *       return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
 *
 *   fingerprint = hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()
 */
export function canonicalize(text: string): string {
  const lines = text
    .normalize("NFC")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((l) => l.replace(/[ \t]+/g, " ").trim());
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
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
