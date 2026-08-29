# 接口契约：知识库管理

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

## 通用约定

- 所有端点要求 `Authorization: Bearer <jwt>`，且角色为**管理员**（角色模型见 003 特性契约）。
- 未鉴权返回 401；非管理员返回 403。
- 文件大小上限默认 20MB，通过 `max_upload_size_mb` 配置。

## 端点

### POST /api/knowledge/upload

上传文档并触发后台异步入库。

- 请求：`multipart/form-data`，字段 `file`（文件流）。
- 响应 `202 Accepted`（立即返回，不等待后台处理）：

```json
{
  "doc_id": 5,
  "doc_name": "FAQ.md",
  "status": "处理中",
  "upload_time": "2026-08-29T10:00:00"
}
```

**校验失败响应**：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 格式不支持（如 `.exe`/`.zip`） | 400 | `{ "code": "unsupported_format", "message": "仅支持 txt 与 markdown 格式" }` |
| 空文件 / 全空白 | 400 | `{ "code": "empty_file", "message": "文件内容为空" }` |
| 超过大小上限 | 413 | `{ "code": "file_too_large", "message": "文件大小超过 20MB 上限" }` |

### GET /api/knowledge/list

知识库列表（分页）。

- 查询参数：`page`（默认 1）、`page_size`（默认 20）。
- 响应：

```json
{
  "total": 42,
  "items": [
    { "doc_id": 5, "doc_name": "FAQ.md", "status": "就绪", "upload_time": "2026-08-29T10:00:00", "fail_msg": null }
  ]
}
```

### GET /api/knowledge/{doc_id}

单文档详情（含失败原因）。

```json
{
  "doc_id": 5,
  "doc_name": "FAQ.md",
  "status": "失败",
  "fail_msg": "文本抽取失败：文件编码无法识别（expected utf-8）",
  "upload_time": "2026-08-29T10:00:00"
}
```

- 不存在返回 404 `{ "code": "doc_not_found", "message": "文档不存在" }`。

### DELETE /api/knowledge/{doc_id}

删除文档（事务性级联清理：原始文件 + MySQL 元数据 + 全部向量切片）。

- 响应 `204 No Content`。
- 不存在返回 404。
- 对「处理中」文档：标记取消，后台任务收敛后完成清理（见 [data-model.md](../data-model.md) 的 ParseTask 状态流转）。

## 状态码与错误码汇总

| HTTP | code | 说明 |
|---|---|---|
| 400 | `unsupported_format` / `empty_file` | 上传校验失败 |
| 401 | `unauthorized` | 未鉴权 |
| 403 | `forbidden` | 非管理员 |
| 404 | `doc_not_found` | 文档不存在 |
| 413 | `file_too_large` | 超大小上限 |

## 配置契约（system_config / .env）

| 配置项 | key | 默认值 | 说明 |
|---|---|---|---|
| 上传大小上限 | `max_upload_size_mb` | 20 | FR-010 |
| 切分块大小 | `chunk_size` | 500 | 与 001 检索一致 |
| 切分重叠 | `chunk_overlap` | 80 | 与 001 检索一致 |
| 任务超时守卫 | `parse_timeout_seconds` | 600 | SC-004 防卡死 |
| 向量化批大小 | `embedding_batch_size` | 16 | SC-002 性能 |
