"""应用统一配置。

配置来源分层（与 specs/006 三层配置设计一致）：
1. `.env` 环境变量（密钥类 + 基础参数）——本模块经 pydantic-settings 加载；
2. `system_config` 表（运行时热调参数，如 rag_top_k / 意图阈值）——由
   `app.services.config_service` 读取覆盖，未覆盖时回落到本模块默认值。

约定：所有密钥仅存环境变量，禁止硬编码；`.env.example` 提供占位模板。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 数据库 ----------
    database_url: str = (
        "mysql+pymysql://root:123456@localhost:3306/nexus_support?charset=utf8mb4"
    )

    # ---------- 003 用户鉴权 ----------
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"  # 必填，≥32 字节
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    min_password_length: int = 8
    phone_regex: str = r"^1[3-9]\d{9}$"
    login_fail_threshold: int = 5
    login_lock_max_seconds: int = 300
    daily_quota_limit: int = 100
    admin_account: str = "admin"  # 预置管理员账号标识（启动时置 admin 角色）
    admin_password: str = "admin123456"  # 仅开发预置用，生产必须修改

    # ---------- 004 会话与消息 ----------
    session_page_size: int = 20
    message_page_size: int = 20
    message_page_size_max: int = 100
    default_session_title: str = "新会话"
    session_title_summary_len: int = 20
    context_turns: int = 6  # 与 001 共用

    # ---------- 002 知识库 ----------
    max_upload_size_mb: int = 20
    chunk_size: int = 500
    chunk_overlap: int = 80
    parse_timeout_seconds: int = 600
    embedding_batch_size: int = 16
    upload_dir: str = "./storage/uploaded"  # 原始文件存储目录（生产可换对象存储）

    # ---------- 001 RAG 问答 ----------
    rag_top_k: int = 6
    rag_candidate_k: int = 20  # 粗筛候选池规模（RRF 融合后、Reranker 精排前）
    rag_bm25_top_k: int = 20  # BM25 单路召回上限
    rag_rrf_k: int = 60  # RRF 融合常数 k
    rag_reranker_enabled: bool = True
    rag_reranker_model: str = "BAAI/bge-reranker-v2-m3"  # sentence-transformers CrossEncoder
    rag_similarity_threshold: float = 0.55
    context_max_tokens: int = 6000
    llm_timeout_seconds: int = 60
    llm_first_token_timeout: int = 30

    # ---------- 005 用户反馈 ----------
    feedback_max_length: int = 200

    # ---------- 006 意图识别 ----------
    intent_high_threshold: float = 0.9
    intent_low_threshold: float = 0.6
    intent_clarify_retry: int = 1
    intent_reverse_calibrate: bool = True
    intent_model_self_check: bool = False
    deepseek_api_key: str = ""  # .env 占位，用户填写
    deepseek_base_url: str = ""
    deepseek_small_model: str = "DeepSeek-R1-0528-Qwen3-8B"
    deepseek_large_model: str = ""

    # ---------- 向量库 / Embedding / LLM ----------
    chroma_dir: str = "./chroma_data"  # Chroma 本地文件模式目录
    embedding_backend: str = "ollama"  # local(本地模型) | ollama(经 Ollama 提供)
    llm_backend: str = "ollama"  # ollama(本地) | deepseek(OpenAI 兼容 API)
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    ollama_chat_model: str = "qwen2"
    # 当 embedding_backend=local 时，加载 sentence-transformers 模型名
    local_embed_model: str = "BAAI/bge-m3"

    # ---------- 日志 ----------
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
