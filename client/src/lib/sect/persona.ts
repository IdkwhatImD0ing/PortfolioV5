/**
 * The voice agent's persona for the sect: the Sun Moon Divine Cult's sound-transmission, a guide that
 * talks about Bill in the third person (server/personas.py, server/prompts_sect.py).
 *
 * The orb sends the same create-web-call and /api/chat requests from any page, so the API routes pick
 * the persona by the request's Referer: a same-origin fetch carries the page's URL (the site sets no
 * Referrer-Policy, so the browser default, strict-origin-when-cross-origin, keeps the path). The sect
 * is the home page, so the routes give its persona to "/" and to the sect's old address, /sect (which
 * now redirects to "/"). A request from anywhere else, or with no Referer at all, asks for nothing
 * and the backend keeps the classic persona.
 *
 * Pure: no React, no three.js, no Next.
 */

/**
 * The backend's name for the sect persona (server/personas.py MING_SECT). It keeps the sect's first
 * name, the Ming Sect (the sect is now 日月神教, the Sun Moon Divine Cult): the API routes and the
 * backend agree on it, and a call already placed carries it.
 */
export const SECT_PERSONA = "ming-sect";

/** True for the sect's pages: the home page "/" and the old "/sect" address ("/sect/", "/sect/x"), not "/sectarian". */
export function isSectPath(pathname: string): boolean {
  return pathname === "/" || pathname === "/sect" || pathname.startsWith("/sect/");
}

/** The persona to ask for, given a request's Referer header: the sect's on the sect's pages, else null. */
export function personaForReferer(referer: string | null | undefined): string | null {
  if (!referer) return null;
  try {
    return isSectPath(new URL(referer).pathname) ? SECT_PERSONA : null;
  } catch {
    // Not a URL (a stripped or malformed header): nothing to go on.
    return null;
  }
}
