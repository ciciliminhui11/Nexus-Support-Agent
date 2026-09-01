import "@testing-library/jest-dom/vitest";

// jsdom 环境补齐 matchMedia（AntD 响应式组件需要）
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = window.matchMedia || function matchMedia(query: string) {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList;
  };
}
