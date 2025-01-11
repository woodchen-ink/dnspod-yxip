import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 腾讯云API配置
SECRET_ID = os.getenv("TENCENT_SECRET_ID")
SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

# API接口配置
API_URL = "https://api.vvhan.com/tool/cf_ip"

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 获取所有域名配置
DOMAINS = []
index = 1
while True:
    domain = os.getenv(f"DOMAIN_{index}")
    if not domain:
        break

    DOMAINS.append(
        {
            "domain": domain,
            "sub_domain": os.getenv(f"SUB_DOMAIN_{index}", "@"),
            "record_type": os.getenv(f"RECORD_TYPE_{index}", "A"),
            "remark": os.getenv(f"REMARK_{index}", "优选IP"),
            "ttl": int(os.getenv(f"TTL_{index}", "600")),
            "update_interval": int(os.getenv(f"UPDATE_INTERVAL_{index}", "15")),
            "ipv4_enabled": os.getenv(f"IPV4_ENABLED_{index}", "true").lower()
            == "true",
            "ipv6_enabled": os.getenv(f"IPV6_ENABLED_{index}", "true").lower()
            == "true",
            "enabled": os.getenv(f"ENABLED_{index}", "true").lower() == "true",
        }
    )
    index += 1
