/**
 * B+4.3.1b Smoke-Test: candidatesApi-Client.
 *
 * Prueft URL-Bau und PATCH-Body. Echtes Netzwerk wird nicht
 * aufgerufen — ``@/lib/api`` ist gemockt.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => ({
  apiMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: mocks.apiMock,
}));

// eslint-disable-next-line import/first
import { fetchCandidates, updatePositionEp } from "@/lib/candidatesApi";

describe("candidatesApi", () => {
  beforeEach(() => {
    mocks.apiMock.mockReset();
  });

  test("fetchCandidates: builds correct URL with explicit limit", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      position_id: "pos-1",
      position_name: "W112",
      materials: [],
    });
    await fetchCandidates("lv-abc", "pos-1", 5);
    expect(mocks.apiMock).toHaveBeenCalledTimes(1);
    const [path] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-abc/positions/pos-1/candidates?limit=5");
  });

  test("fetchCandidates: default limit is 3", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      position_id: "pos-2",
      position_name: "W628A",
      materials: [],
    });
    await fetchCandidates("lv-xyz", "pos-2");
    const [path] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-xyz/positions/pos-2/candidates?limit=3");
  });

  test("updatePositionEp: sends PATCH with ep body", async () => {
    mocks.apiMock.mockResolvedValueOnce(undefined);
    await updatePositionEp("lv-1", "pos-1", 42.5);
    expect(mocks.apiMock).toHaveBeenCalledTimes(1);
    const [path, opts] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/lv-1/positions/pos-1");
    expect(opts.method).toBe("PATCH");
    expect(opts.body).toEqual({ ep: 42.5 });
  });
});
