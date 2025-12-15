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

    # WeChat credentials (from environment)
    WECHAT_APPID = os.environ.get("WECHAT_APPID") or os.environ.get("WECHAT_APP_ID") or "wx75cdd8fc1ca68c69"
    WECHAT_SECRET = os.environ.get("WECHAT_SECRET") or os.environ.get("WECHAT_APP_SECRET") or "d50cb0a992515238c9807950fed29bf1"
    WECHAT_TASK_TEMPLATE_ID = os.environ.get("WECHAT_TASK_TEMPLATE_ID", "GElWxP8srvY_TwH-h69q4XcmgLyNZBsvjp6rSt8dhUU")
