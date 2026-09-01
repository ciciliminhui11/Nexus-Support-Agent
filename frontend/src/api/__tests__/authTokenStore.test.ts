/**
 * sessionStorage 令牌读写单测。
 */
import { beforeEach, describe, expect, it } from "vitest";
import { clearToken, getToken, setToken } from "@/api/authTokenStore";

describe("authTokenStore", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("set → get 往返", () => {
    expect(getToken()).toBeNull();
    setToken("jwt.abc.123");
    expect(getToken()).toBe("jwt.abc.123");
  });

  it("clear 后读取为 null", () => {
    setToken("token");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("不同令牌互不干扰（覆盖写）", () => {
    setToken("first");
    setToken("second");
    expect(getToken()).toBe("second");
  });
});
