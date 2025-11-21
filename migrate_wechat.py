"""
数据库迁移脚本：为微信小程序集成添加必要字段

执行方式：
python migrate_wechat.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def run_migration():
    """执行数据库迁移"""
    with app.app_context():
        print("开始数据库迁移...")
        
        # 1. 为 User 表添加微信字段
        print("\n1. 为 User 表添加微信相关字段...")
        try:
            with db.engine.connect() as conn:
                # 添加 wechat_openid
                conn.execute(text("""
                    ALTER TABLE user ADD COLUMN wechat_openid TEXT;
                """))
                conn.commit()
                print("  ✓ 已添加 wechat_openid 字段")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("  - wechat_openid 字段已存在，跳过")
            else:
                print(f"  ✗ 添加 wechat_openid 失败: {e}")
        
        try:
            with db.engine.connect() as conn:
                # 添加 wechat_unionid
                conn.execute(text("""
                    ALTER TABLE user ADD COLUMN wechat_unionid TEXT;
                """))
                conn.commit()
                print("  ✓ 已添加 wechat_unionid 字段")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("  - wechat_unionid 字段已存在，跳过")
            else:
                print(f"  ✗ 添加 wechat_unionid 失败: {e}")
        
        try:
            with db.engine.connect() as conn:
                # 添加 wechat_nickname
                conn.execute(text("""
                    ALTER TABLE user ADD COLUMN wechat_nickname TEXT;
                """))
                conn.commit()
                print("  ✓ 已添加 wechat_nickname 字段")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("  - wechat_nickname 字段已存在，跳过")
            else:
                print(f"  ✗ 添加 wechat_nickname 失败: {e}")
        
        # 2. 为 StudentProfile 表添加微信字段
        print("\n2. 为 StudentProfile 表添加微信相关字段...")
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE student_profile ADD COLUMN wechat_openid TEXT;
                """))
                conn.commit()
                print("  ✓ 已添加 wechat_openid 字段")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("  - wechat_openid 字段已存在，跳过")
            else:
                print(f"  ✗ 添加 wechat_openid 失败: {e}")
        
        # 3. 为 Task 表添加学生提交相关字段
        print("\n3. 为 Task 表添加学生提交相关字段...")
        fields_to_add = [
            ("student_submitted", "INTEGER DEFAULT 0"),
            ("submitted_at", "TIMESTAMP"),
            ("evidence_photos", "TEXT"),  # JSON 数组
            ("student_note", "TEXT"),
        ]
        
        for field_name, field_type in fields_to_add:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(f"""
                        ALTER TABLE task ADD COLUMN {field_name} {field_type};
                    """))
                    conn.commit()
                    print(f"  ✓ 已添加 {field_name} 字段")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print(f"  - {field_name} 字段已存在，跳过")
                else:
                    print(f"  ✗ 添加 {field_name} 失败: {e}")
        
        # 4. 创建家长-学生关联表
        print("\n4. 创建 parent_student_link 表...")
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS parent_student_link (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id INTEGER NOT NULL,
                        student_name TEXT NOT NULL,
                        relation TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1,
                        FOREIGN KEY (parent_id) REFERENCES user (id),
                        UNIQUE(parent_id, student_name)
                    );
                """))
                conn.commit()
                print("  ✓ 已创建 parent_student_link 表")
        except Exception as e:
            print(f"  ✗ 创建 parent_student_link 表失败: {e}")
        
        print("\n✅ 数据库迁移完成！")
        print("\n可以开始开发微信小程序后端 API 了。")

if __name__ == "__main__":
    run_migration()
