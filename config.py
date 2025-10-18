import os

# 获取当前文件所在的文件夹路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 用于 Flask 的安全密钥（后面我们可以改成更安全的随机值）
    SECRET_KEY = "dev-key-change-later"

    # 数据库路径：在当前项目文件夹下自动生成 app.db
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "app.db")

    # 关闭不必要的警告
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 证据文件保存目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
