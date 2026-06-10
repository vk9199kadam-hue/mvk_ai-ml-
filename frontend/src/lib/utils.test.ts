import { describe, it, expect } from "vitest";
import { cn, formatBytes, formatDuration, getConfidenceColor, getConfidenceBadge, truncate } from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("merges tailwind classes correctly", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
  });
});

describe("formatBytes", () => {
  it("formats 0 bytes", () => {
    expect(formatBytes(0)).toBe("0 Bytes");
  });

  it("formats kilobytes", () => {
    expect(formatBytes(1024)).toBe("1 KB");
  });

  it("formats megabytes", () => {
    expect(formatBytes(1048576)).toBe("1 MB");
  });

  it("formats gigabytes", () => {
    expect(formatBytes(1073741824)).toBe("1 GB");
  });

  it("handles decimal values", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
});

describe("formatDuration", () => {
  it("formats milliseconds", () => {
    expect(formatDuration(500)).toBe("500ms");
  });

  it("formats seconds", () => {
    expect(formatDuration(1500)).toBe("1.5s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(125000)).toBe("2m 5s");
  });
});

describe("getConfidenceColor", () => {
  it("returns green for high confidence", () => {
    expect(getConfidenceColor(0.95)).toContain("green");
  });

  it("returns yellow for medium confidence", () => {
    expect(getConfidenceColor(0.75)).toContain("yellow");
  });

  it("returns orange for low confidence", () => {
    expect(getConfidenceColor(0.6)).toContain("orange");
  });

  it("returns red for very low confidence", () => {
    expect(getConfidenceColor(0.4)).toContain("red");
  });
});

describe("getConfidenceBadge", () => {
  it("returns Auto-Approved for >= 0.9", () => {
    expect(getConfidenceBadge(0.95)).toContain("Auto-Approved");
  });

  it("returns Manual Approval for 0.7-0.89", () => {
    expect(getConfidenceBadge(0.8)).toContain("Manual Approval");
  });

  it("returns Review Required for 0.5-0.69", () => {
    expect(getConfidenceBadge(0.6)).toContain("Review Required");
  });

  it("returns Advisory Only for < 0.5", () => {
    expect(getConfidenceBadge(0.3)).toContain("Advisory Only");
  });
});

describe("truncate", () => {
  it("returns string as-is if shorter than length", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("truncates long strings", () => {
    const result = truncate("hello world this is long", 10);
    expect(result).toBe("hello worl...");
    expect(result.length).toBe(13);
  });
});
