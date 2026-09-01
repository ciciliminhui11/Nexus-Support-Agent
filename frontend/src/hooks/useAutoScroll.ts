/**
 * 近底部自动滚动（T025）：内容变化时若用户仍贴近底部则滚动到底；
 * 用户主动上滚后暂停跟随。
 */
import { useEffect, useRef } from "react";

const BOTTOM_THRESHOLD = 80;

export function useAutoScroll<T extends HTMLElement>(dependencies: readonly unknown[]) {
  const ref = useRef<T>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    const el = ref.current;
    if (!el || !stickToBottom.current) return;
    el.scrollTop = el.scrollHeight;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottom.current = distance < BOTTOM_THRESHOLD;
  };

  return { ref, onScroll };
}
