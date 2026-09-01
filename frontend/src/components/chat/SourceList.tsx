/**
 * 引用来源展示（T027）：文档名 + 片段摘要，可点击展开。
 */
import { Collapse } from "antd";
import type { Source } from "@/types";

interface SourceListProps {
  sources: Source[];
}

export default function SourceList({ sources }: SourceListProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <Collapse
      ghost
      size="small"
      items={[
        {
          key: "sources",
          label: `引用来源（${sources.length}）`,
          children: (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {sources.map((s, i) => (
                <li key={i} style={{ marginBottom: 6 }}>
                  <strong>{s.doc_name}</strong>
                  {s.snippet ? (
                    <div style={{ color: "rgba(0,0,0,0.65)", fontSize: 13, marginTop: 2 }}>
                      {s.snippet}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ),
        },
      ]}
    />
  );
}
