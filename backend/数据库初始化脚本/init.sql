-- =============================================================
-- AI 智能客服系统 数据库初始化脚本（MySQL 8.0）
-- 建表语句 + 初始数据（system_config 默认值）
-- 执行：mysql -u root -p < init.sql
-- 说明：管理员账号由后端启动时按 .env ADMIN_ACCOUNT 预置（密码哈希需在
--       应用内生成），不在此脚本硬编码明文。
-- =============================================================

CREATE DATABASE IF NOT EXISTS nexus_support DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nexus_support;

-- ---------- 003 用户鉴权 ----------
CREATE TABLE IF NOT EXISTS `user` (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_identifier  VARCHAR(100) NOT NULL COMMENT '账号标识：手机号或邮箱',
    account_type        ENUM('phone','email') NOT NULL COMMENT '账号类型',
    password_hash       VARCHAR(255) NOT NULL COMMENT 'bcrypt 加盐哈希，禁止明文',
    role                ENUM('user','admin') NOT NULL DEFAULT 'user',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_identifier (account_identifier)
) ENGINE=InnoDB COMMENT='用户表';

CREATE TABLE IF NOT EXISTS user_quota_daily (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT NOT NULL COMMENT 'FK user.id',
    stat_date   DATE NOT NULL COMMENT '统计日期',
    count       INT NOT NULL DEFAULT 0 COMMENT '当日已用提问次数',
    UNIQUE KEY uq_user_quota_daily (user_id, stat_date),
    CONSTRAINT fk_quota_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB COMMENT='用户每日提问计数';

-- ---------- 004 会话与消息 ----------
CREATE TABLE IF NOT EXISTS `session` (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    title       VARCHAR(100) NOT NULL COMMENT '会话标题',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_session_user_time (user_id, create_time),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB COMMENT='会话表';

CREATE TABLE IF NOT EXISTS `message` (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id       BIGINT NOT NULL,
    role             ENUM('user','ai') NOT NULL COMMENT '消息角色',
    content          TEXT NOT NULL COMMENT '消息正文',
    reference_source JSON NULL COMMENT 'AI回答引用来源数组',
    intent_label     VARCHAR(50) NULL COMMENT '意图标签',
    create_time      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_message_session_time_id (session_id, create_time, id),
    CONSTRAINT fk_message_session FOREIGN KEY (session_id) REFERENCES `session`(id)
) ENGINE=InnoDB COMMENT='消息表';

-- ---------- 002 知识库 ----------
CREATE TABLE IF NOT EXISTS knowledge_doc (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_name    VARCHAR(255) NOT NULL COMMENT '原始文件名（含扩展名）',
    file_path   VARCHAR(500) NOT NULL COMMENT '原始文件存储路径',
    status      ENUM('处理中','就绪','失败') NOT NULL DEFAULT '处理中',
    fail_msg    VARCHAR(1000) NULL COMMENT '失败原因',
    upload_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_knowledge_status (status),
    KEY ix_knowledge_upload_time (upload_time)
) ENGINE=InnoDB COMMENT='知识库文档元数据';

CREATE TABLE IF NOT EXISTS parse_task (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_id      BIGINT NOT NULL,
    status      ENUM('处理中','成功','失败','已取消') NOT NULL DEFAULT '处理中',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finish_time DATETIME NULL,
    fail_msg    VARCHAR(1000) NULL,
    KEY ix_parsetask_status (status),
    CONSTRAINT fk_parsetask_doc FOREIGN KEY (doc_id) REFERENCES knowledge_doc(id)
        ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='文档解析任务';

-- ---------- 005 用户反馈 ----------
CREATE TABLE IF NOT EXISTS feedback (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id    BIGINT NOT NULL COMMENT 'FK message.id（不级联删除）',
    user_id       BIGINT NOT NULL COMMENT 'FK user.id',
    feedback_type ENUM('like','dislike') NOT NULL,
    feedback_text VARCHAR(500) NULL COMMENT '可选文字说明',
    create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_feedback_message_user (message_id, user_id),
    CONSTRAINT fk_feedback_message FOREIGN KEY (message_id) REFERENCES `message`(id),
    CONSTRAINT fk_feedback_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB COMMENT='用户反馈（消息删除后保留，供统计）';

-- ---------- 公共：运行时配置 ----------
CREATE TABLE IF NOT EXISTS system_config (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    `key`      VARCHAR(100) NOT NULL,
    value      VARCHAR(500) NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_system_config_key (`key`)
) ENGINE=InnoDB COMMENT='运行时热调参数（key-value，未配置回落 app/config.py 默认值）';

-- ---------- 初始数据：system_config 默认值 ----------
INSERT INTO system_config (`key`, `value`) VALUES
    ('jwt_expire_hours', '24'),
    ('min_password_length', '8'),
    ('login_fail_threshold', '5'),
    ('login_lock_max_seconds', '300'),
    ('daily_quota_limit', '100'),
    ('session_page_size', '20'),
    ('message_page_size', '20'),
    ('message_page_size_max', '100'),
    ('default_session_title', '新会话'),
    ('session_title_summary_len', '20'),
    ('context_turns', '6'),
    ('max_upload_size_mb', '20'),
    ('chunk_size', '500'),
    ('chunk_overlap', '80'),
    ('parse_timeout_seconds', '600'),
    ('embedding_batch_size', '16'),
    ('rag_top_k', '6'),
    ('rag_candidate_k', '20'),
    ('rag_bm25_top_k', '20'),
    ('rag_rrf_k', '60'),
    ('rag_reranker_enabled', 'true'),
    ('rag_reranker_model', 'BAAI/bge-reranker-v2-m3'),
    ('rag_similarity_threshold', '0.55'),
    ('context_max_tokens', '6000'),
    ('llm_timeout_seconds', '60'),
    ('llm_first_token_timeout', '30'),
    ('feedback_max_length', '200'),
    ('intent_high_threshold', '0.9'),
    ('intent_low_threshold', '0.6'),
    ('intent_clarify_retry', '1'),
    ('intent_reverse_calibrate', 'true'),
    ('intent_model_self_check', 'false')
ON DUPLICATE KEY UPDATE value = VALUES(value);
