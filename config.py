"""
IPTV Web客户端配置文件
"""

# 应用程序配置
APP_NAME = "IPTV Web客户端"
DEBUG = False
PORT = 12000

# 登录凭据
USERNAME = "admin"
PASSWORD = "User1234"

# 文件上传配置
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
UPLOAD_FOLDER = "uploads"

# 频道文件
CHANNELS_FILE = "channels.json"