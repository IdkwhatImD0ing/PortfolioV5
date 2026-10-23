/**
 * GET /sect: the sect moved to the home page (app/page.tsx), so the old address redirects there for
 * good (308), keeping the query string (?view=page, ?open=, ?frame=, ?tier=, ?debug=). The browser
 * keeps the #hash itself across a redirect, so /sect#forge lands on /#forge. Only /sect itself:
 * /sect/music.json and the scene's files under public/sect/ are served as before.
 */
import { NextResponse, type NextRequest } from "next/server";

export function GET(request: NextRequest): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = "/";
  return NextResponse.redirect(url, 308);
}

export const HEAD = GET;
