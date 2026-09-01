/**
 * 会话列表组件单测：渲染会话项 / 空标题兜底 / 空态 / 点击切换 / 新建。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SessionList from "@/components/session/SessionList";
import type { Session } from "@/types";

const sessions: Session[] = [
  { session_id: 1, title: "退货咨询", create_time: "2026-08-01T00:00:00Z" },
  { session_id: 2, title: "", create_time: "2026-08-02T00:00:00Z" },
];

describe("SessionList", () => {
  it("渲染会话标题，空标题兜底为「新会话」", () => {
    render(
      <SessionList sessions={sessions} activeSessionId={1} onSelect={() => {}} onNewSession={() => {}} />,
    );
    expect(screen.getByText("退货咨询")).toBeInTheDocument();
    expect(screen.getByText("新会话")).toBeInTheDocument();
    expect(screen.getByText("新建会话")).toBeInTheDocument();
  });

  it("点击会话项触发 onSelect（携带 session_id）", () => {
    const onSelect = vi.fn();
    render(
      <SessionList sessions={sessions} activeSessionId={null} onSelect={onSelect} onNewSession={() => {}} />,
    );
    fireEvent.click(screen.getByText("退货咨询"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("点击「新建会话」触发 onNewSession", () => {
    const onNewSession = vi.fn();
    render(
      <SessionList sessions={[]} activeSessionId={null} onSelect={() => {}} onNewSession={onNewSession} />,
    );
    fireEvent.click(screen.getByText("新建会话"));
    expect(onNewSession).toHaveBeenCalled();
  });

  it("无会话时展示空态提示", () => {
    render(
      <SessionList sessions={[]} activeSessionId={null} onSelect={() => {}} onNewSession={() => {}} />,
    );
    expect(screen.getByText("暂无会话，点击上方新建")).toBeInTheDocument();
  });
});
