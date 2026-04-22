/**
 * B+4.3.1c Smoke-Test: gapsApi-Client.
 *
 * Prueft URL-Shape mit und ohne Query-Param. Das echte Netzwerk wird
 * nicht aufgerufen — ``@/lib/api`` ist gemockt.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => ({
  apiMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: mocks.apiMock,
}));

// eslint-disable-next-line import/first
import { fetchGaps } from "@/lib/gapsApi";

describe("gapsApi.fetchGaps", () => {
  beforeEach(() => {
    mocks.apiMock.mockReset();
  });

  test("default (no query param) builds plain /gaps URL", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      lv_id: "lv-1",
      total_positions: 0,
      total_materials: 0,
      gaps_count: 0,
      missing_count: 0,
      estimated_count: 0,
      low_confidence_count: 0,
      gaps: [],
    });
    await fetchGaps("lv-1");
    expect(mocks.apiMock).toHaveBeenCalledTimes(1);
    const [path] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-1/gaps");
  });

  test("includeLowConfidence=true appends the query param", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      lv_id: "lv-2",
      total_positions: 0,
      total_materials: 0,
      gaps_count: 0,
      missing_count: 0,
      estimated_count: 0,
      low_confidence_count: 0,
      gaps: [],
    });
    await fetchGaps("lv-2", true);
    const [path] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-2/gaps?include_low_confidence=true");
  });

  test("includeLowConfidence=false behaves like default (no param)", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      lv_id: "lv-3",
      total_positions: 0,
      total_materials: 0,
      gaps_count: 0,
      missing_count: 0,
      estimated_count: 0,
      low_confidence_count: 0,
      gaps: [],
    });
    await fetchGaps("lv-3", false);
    const [path] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-3/gaps");
    // Explicit negative: kein ?include_low_confidence=false
    expect(path).not.toContain("include_low_confidence=false");
  });
});
