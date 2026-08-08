import { createHmac } from 'node:crypto';

/**
 * Minimal RFC 6238 TOTP generator (SHA-1, 6 digits, 30s period) so the
 * E2E suite can complete the real MFA login challenge for seeded
 * accounts (the seed exports the plaintext base32 secret, e.g.
 * E2E_PARENT_TOTP_SECRET). No external otp dependency needed —
 * Playwright specs run under Node, so node:crypto is available.
 */

const B32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

function base32Decode(secret: string): Buffer {
  const clean = secret.toUpperCase().replace(/=+$/g, '').replace(/\s+/g, '');
  let bits = 0;
  let value = 0;
  const out: number[] = [];
  for (const ch of clean) {
    const idx = B32_ALPHABET.indexOf(ch);
    if (idx === -1) throw new Error(`totp: invalid base32 character "${ch}"`);
    value = (value << 5) | idx;
    bits += 5;
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(out);
}

export function totpCode(secret: string, epochMs: number = Date.now()): string {
  const counter = Math.floor(epochMs / 1000 / 30);
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(counter));
  const digest = createHmac('sha1', base32Decode(secret)).update(msg).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const bin =
    ((digest[offset] & 0x7f) << 24) |
    (digest[offset + 1] << 16) |
    (digest[offset + 2] << 8) |
    digest[offset + 3];
  return String(bin % 1_000_000).padStart(6, '0');
}
