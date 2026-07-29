/**
 * The View button on the dashboard nudge navigated nowhere: the backend stores
 * a resolved href ("/stock/OGDC") but TanStack Router's `to` takes a route
 * pattern ("/stock/$ticker") plus params, so nothing in the route tree matched.
 */
import { describe, it, expect } from "vitest";
import { viewTargetLink } from "./view-target";

describe("viewTargetLink", () => {
  it("splits a resolved stock href into the route pattern and its params", () => {
    expect(viewTargetLink("/stock/OGDC")).toEqual({
      to: "/stock/$ticker",
      params: { ticker: "OGDC" },
    });
  });

  it("upper-cases the ticker so /stock/ogdc resolves the same route", () => {
    expect(viewTargetLink("/stock/ogdc")).toEqual({
      to: "/stock/$ticker",
      params: { ticker: "OGDC" },
    });
  });

  it("passes /finance through", () => {
    expect(viewTargetLink("/finance")).toEqual({ to: "/finance" });
  });

  it("falls back to /finance rather than throwing on junk", () => {
    // view_target is backend-computed, but a cached row from an older deploy
    // (or a route we later rename) must land somewhere useful, not crash.
    for (const junk of [null, undefined, "", "  ", "/nope", "/stock/", "javascript:alert(1)"]) {
      expect(viewTargetLink(junk)).toEqual({ to: "/finance" });
    }
  });
});
