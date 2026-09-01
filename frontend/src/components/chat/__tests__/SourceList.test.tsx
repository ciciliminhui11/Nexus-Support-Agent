/**
 * 引用来源组件单测：空数组不渲染、有来源渲染折叠标题。
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SourceList from "@/components/chat/SourceList";
import type { Source } from "@/types";

describe("SourceList", () => {
  it("无来源时不渲染", () => {
    const { container } = render(<SourceList sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("有来源时渲染数量标签", () => {
    const sources: Source[] = [
      { doc_name: "退货政策.md", snippet: "支持 7 天无理由退换货……" },
      { doc_name: "配送时效.md", snippet: "华东地区次日达……" },
    ];
    render(<SourceList sources={sources} />);
    expect(screen.getByText("引用来源（2）")).toBeInTheDocument();
  });
});
