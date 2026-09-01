/**
 * 新建会话按钮（T030）。
 */
import { Button } from "antd";
import { PlusOutlined } from "@ant-design/icons";

interface NewSessionButtonProps {
  onClick: () => void;
  loading?: boolean;
}

export default function NewSessionButton({ onClick, loading = false }: NewSessionButtonProps) {
  return (
    <Button type="primary" block icon={<PlusOutlined />} onClick={onClick} loading={loading}>
      新建会话
    </Button>
  );
}
