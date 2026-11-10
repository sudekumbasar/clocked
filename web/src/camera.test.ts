import { describe, expect, it } from "vitest";
import { fitWithin, MAX_LONG_EDGE } from "./camera";

describe("photo size", () => {
  it("scales the long edge down to the limit", () => {
    expect(fitWithin(4032, 3024)).toEqual({ width: MAX_LONG_EDGE, height: 1176 });
    expect(fitWithin(3024, 4032)).toEqual({ width: 1176, height: MAX_LONG_EDGE });
  });

  it("never scales up", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });
});
