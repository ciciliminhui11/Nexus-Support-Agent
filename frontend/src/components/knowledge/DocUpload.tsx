/**
 * 文档上传（US5）：Upload.Dragger 多选，beforeUpload 复用 isAllowedUploadType /
 * isWithinUploadSize（.txt/.md、≤20MB），customRequest 驱动 AntD 内置进度条，
 * 上传成功后由 KnowledgePage 刷新列表。
 */
import { App, Typography, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import {
  MAX_UPLOAD_MB,
  UPLOAD_ALLOWED_EXT,
  isAllowedUploadType,
  isWithinUploadSize,
} from "@/utils/validation";

export interface DocUploadProps {
  /** 是否有上传进行中（禁用再次选择，避免并发歧义） */
  uploading: boolean;
  /** 实际上传：返回 Promise，customRequest 据其成功/失败更新上传列表 */
  onUpload: (file: File, onProgress: (percent: number) => void) => Promise<unknown>;
}

export default function DocUpload({ uploading, onUpload }: DocUploadProps) {
  const { message } = App.useApp();

  const uploadProps: UploadProps = {
    name: "file",
    multiple: true,
    accept: UPLOAD_ALLOWED_EXT.join(","),
    disabled: uploading,
    beforeUpload: (file) => {
      if (!isAllowedUploadType(file.name)) {
        message.error(`不支持的文件类型，仅支持 ${UPLOAD_ALLOWED_EXT.join(" / ")}`);
        return Upload.LIST_IGNORE;
      }
      if (!isWithinUploadSize(file.size)) {
        message.error(`文件超过 ${MAX_UPLOAD_MB}MB 上限`);
        return Upload.LIST_IGNORE;
      }
      return true;
    },
    customRequest: async ({ file, onProgress, onSuccess, onError }) => {
      try {
        await onUpload(file as File, (p) => onProgress?.({ percent: p }));
        onSuccess?.(null);
      } catch (err) {
        onError?.(err as Error);
      }
    },
  };

  return (
    <div>
      <Upload.Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
        <p className="ant-upload-hint">
          支持 {UPLOAD_ALLOWED_EXT.join(" / ")} 格式，单个文件不超过 {MAX_UPLOAD_MB}MB
        </p>
      </Upload.Dragger>
      <Typography.Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
        上传后进入「处理中」状态，完成后可在问答中作为知识引用。
      </Typography.Paragraph>
    </div>
  );
}
