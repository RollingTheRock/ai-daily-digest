/** Cryptographic utilities for URL signature verification */

import { createHmac, timingSafeEqual } from "crypto";

const SECRET_KEY = process.env.SECRET_KEY || "";

export function verifySignature(
  contentId: string,
  date: string,
  signature: string
): boolean {
  if (!SECRET_KEY) {
    console.error("SECRET_KEY not configured");
    return false;
  }

  const message = `${contentId}:${date}`;
  const expected = createHmac("sha256", SECRET_KEY)
    .update(message, "utf-8")
    .digest("hex")
    .slice(0, 16);

  try {
    const expectedBuf = Buffer.from(expected, "hex");
    const signatureBuf = Buffer.from(signature, "hex");

    if (expectedBuf.length !== signatureBuf.length) {
      return false;
    }

    return timingSafeEqual(expectedBuf, signatureBuf);
  } catch {
    return false;
  }
}

export function generateSignature(contentId: string, date: string): string {
  if (!SECRET_KEY) {
    throw new Error("SECRET_KEY not configured");
  }

  const message = `${contentId}:${date}`;
  return createHmac("sha256", SECRET_KEY)
    .update(message, "utf-8")
    .digest("hex")
    .slice(0, 16);
}
