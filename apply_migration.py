#!/usr/bin/env python
"""
手动数据库迁移脚本 - 为 user 表添加 daily_quota 字段
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import create_engine, text
from app.config import settings

def migrate_database():
    """为 user 表添加 daily_quota 字段"""
    print("正在为 user 表添加 daily_quota 字段...")

    try:
        # 创建数据库引擎
        engine = create_engine(settings.database_url)

        # 检查字段是否存在
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM user LIKE 'daily_quota'"))
            if result.fetchone():
                print("[OK] daily_quota 字段已存在")
                return True

        # 添加字段
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE `user`
                ADD COLUMN daily_quota INT NULL COMMENT '用户自定义每日提问限额，NULL 使用全局默认值'
                AFTER role
            """))
            conn.commit()

        print("[OK] 成功添加 daily_quota 字段")
        return True

    except Exception as e:
        print(f"[FAIL] 添加字段失败: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("数据库迁移完成!")
    else:
        print("数据库迁移失败!")
        sys.exit(1)