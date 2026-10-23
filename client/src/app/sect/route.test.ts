import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { GET, HEAD } from "./route";

describe("GET /sect", () => {
  it("redirects to the home page for good", () => {
    const res = GET(new NextRequest("http://localhost:3000/sect"));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("keeps the query string", () => {
    const res = GET(new NextRequest("https://art3m1s.me/sect?view=page&open=project:dispatchai"));
    expect(res.headers.get("location")).toBe("https://art3m1s.me/?view=page&open=project:dispatchai");
    const test = GET(new NextRequest("http://localhost:3000/sect?frame=1103&tier=high&debug=1"));
    expect(test.headers.get("location")).toBe("http://localhost:3000/?frame=1103&tier=high&debug=1");
  });

  it("answers HEAD the same way", () => {
    expect(HEAD(new NextRequest("http://localhost:3000/sect?tier=low")).headers.get("location")).toBe("http://localhost:3000/?tier=low");
  });
});
