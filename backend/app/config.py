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
    embedding_retry_times: int = 2  # Embedding 批次失败后的有限重试次数（瞬时网络超时兜底）
    embedding_retry_backoff_seconds: float = 0.5  # 线性退避基数（第 n 次重试 sleep 基数×n）
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
    # DeepSeek API 密钥/Base URL 为 001 对话与 006 兜底层共用（同一厂商）。模型分开：
    # 001 对话用 deepseek_chat_model；006 兜底层用 deepseek_large_model（空则回退对话模型）；
    # 006 小模型层用独立 SMALL_MODEL_*（可不同厂商/端点，不复用 DeepSeek 凭据）。
    deepseek_api_key: str = ""  # .env 占位，用户填写
    deepseek_base_url: str = "https://api.deepseek.com"

    # ---------- 向量库 / Embedding / LLM ----------
    chroma_dir: str = "./chroma_data"  # Chroma 本地文件模式目录
    embedding_backend: str = "ollama"  # openai_compat(OpenAI 兼容云端 API) | local(本地模型) | ollama(经 Ollama 提供)
    # openai_compat 后端：OpenAI 兼容 /embeddings（如 SiliconFlow 免费 bge-m3，1024 维）
    embedding_api_base_url: str = ""
    embedding_api_key: str = ""
    embedding_api_model: str = "BAAI/bge-m3"
    llm_backend: str = "deepseek"  # deepseek(OpenAI 兼容 API) | ollama(本地)
    # LLM 统一配置（001 对话 + 006 意图兜底共用）
    llm_model: str = "deepseek-v4-flash"
    llm_base_url: str = "https://api.deepseek.com"
    # 以下为遗留/特殊用途配置
    deepseek_chat_model: str = "deepseek-chat"  # 001 对话 LLM 模型（DeepSeek OpenAI 兼容）
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    ollama_chat_model: str = "qwen2"
    # 006 意图识别小模型层：独立厂商/端点配置（SMALL_MODEL_*），
    # 不复用 DEEPSEEK_* 凭据。三项均空时小模型层短路，直接流转大模型兜底。
    small_model_name: str = ""
    small_model_api_key: str = ""
    small_model_base_url: str = ""
    # 006 大模型兜底层（默认不启用 intent_model_self_check；空则回退 deepseek_chat_model）
    deepseek_large_model: str = ""
    # 006 补充配置：总开关 / 规则配置路径 / 模型调用参数 / 模板话术
    intent_enabled: bool = True  # 意图识别总开关（关闭时识别结果恒为 unknown）
    intent_keywords_path: str = "./config/intent_keywords.yaml"
    intent_patterns_path: str = "./config/intent_patterns.yaml"
    intent_negative_samples_path: str = "./config/intent_negative_samples.yaml"
    intent_llm_timeout_seconds: int = 30  # 意图模型单次请求超时
    intent_llm_max_retries: int = 2  # 429 指数退避重试次数
    intent_small_talk_reply: str = (
        "您好，很高兴为您服务！如果您有任何产品、售后方面的问题，"
        "随时都可以问我哦～"
    )
    intent_complaint_reply: str = (
        "非常抱歉给您带来不好的体验，我们非常重视您的反馈，已为您记录，"
        "稍后会有专属客服与您联系处理，请您耐心等待。"
    )
    # 当 embedding_backend=local 时，加载 sentence-transformers 模型名
    local_embed_model: str = "BAAI/bge-m3"

    # ---------- 008 链路埋点 ----------
    # 采集/落库/打印均只走 Settings（env），不走 system_config 热调（见 research §7）
    trace_enabled: bool = True  # 总开关；关闭时 Tracer 全程短路，零采集零打印零落库
    trace_flush_enabled: bool = True  # 后台批量落库开关（测试置 false）
    trace_flush_interval_seconds: int = 10  # 周期 flush 间隔
    trace_buffer_size: int = 200  # 缓冲阈值，达到即提前 flush
    trace_console_log: bool = True  # 控制台打印可读完整链路块
    trace_retention_days: int = 7  # 保留期；<=0 表示不清理

    # ---------- 日志 ----------
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
