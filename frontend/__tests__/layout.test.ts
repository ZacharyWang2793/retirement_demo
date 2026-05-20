import { describe, expect, it } from "vitest";

import { findNextFreeSlot } from "../lib/layout";

describe("findNextFreeSlot", () => {
  it("returns (0,0) on an empty canvas", () => {
    expect(findNextFreeSlot([], 4, 4)).toEqual({ x: 0, y: 0 });
  });

  it("places the next card to the right when there's room", () => {
    const layout = [{ i: "a", x: 0, y: 0, w: 4, h: 4 }];
    expect(findNextFreeSlot(layout, 4, 4)).toEqual({ x: 4, y: 0 });
  });

  it("wraps to next row when the row is full", () => {
    const layout = [
      { i: "a", x: 0, y: 0, w: 6, h: 4 },
      { i: "b", x: 6, y: 0, w: 6, h: 4 },
    ];
    expect(findNextFreeSlot(layout, 6, 4)).toEqual({ x: 0, y: 4 });
  });

  it("finds a small gap between large cards", () => {
    const layout = [
      { i: "a", x: 0, y: 0, w: 6, h: 8 },
      { i: "b", x: 8, y: 0, w: 4, h: 8 },
    ];
    // Slot from x=6, y=0 with w=2,h=4 should fit
    expect(findNextFreeSlot(layout, 2, 4)).toEqual({ x: 6, y: 0 });
  });
});
