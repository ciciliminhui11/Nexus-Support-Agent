# 后端（Backend）

> ⚠️ 骨架阶段：代码尚未编写，以下为计划内容，待补充。

## 技术栈

- Python FastAPI（异步原生，对 SSE 流式输出友好）
- SQLAlchemy + MySQL 8.0
- Chroma 向量数据库（本地文件模式）
- 详见 [`../初步设计方案.txt`](../初步设计方案.txt)

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `app/` | FastAPI 应用源码（规划为包结构，具体分层待编码时确定） |
| `数据库初始化脚本/` | 建表语句 + 初始数据（`*.sql`） |
| `requirements.txt` | Python 依赖清单 |
| `README.md` | 本文件：启动说明（含 API Key 配置方式） |

## 启动说明

> 待补充

## API Key / 模型配置方式

> 待补充：通过环境变量（`.env`）配置，提供 `.env.example` 示例，真实密钥禁止提交仓库。
