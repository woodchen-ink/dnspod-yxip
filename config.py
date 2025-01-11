import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# DNSPOD API配置
DNSPOD_ID = os.getenv("DNSPOD_ID")
DNSPOD_TOKEN = os.getenv("DNSPOD_TOKEN")

# API接口配置
API_URL = "https://api.vvhan.com/tool/cf_ip"

# 默认配置
DEFAULT_TTL = 600
DEFAULT_UPDATE_INTERVAL = 15

# 支持的线路类型
LINE_TYPES = ["默认", "移动", "联通", "电信"]

# 支持的记录类型
RECORD_TYPES = ["A", "AAAA"]

# 域名配置
DOMAINS = []

# 从环境变量加载域名配置
i = 1
while True:
    domain_key = f"DOMAIN_{i}"
    if not os.getenv(domain_key):
        break

    # 获取基本配置
    base_config = {
        "domain": os.getenv(domain_key),
        "sub_domain": os.getenv(f"SUB_DOMAIN_{i}", "@"),
        "line": LINE_TYPES,
        "ttl": int(os.getenv(f"TTL_{i}", str(DEFAULT_TTL))),
        "update_interval": int(
            os.getenv(f"UPDATE_INTERVAL_{i}", str(DEFAULT_UPDATE_INTERVAL))
        ),
        "enabled": os.getenv(f"ENABLED_{i}", "true").lower() == "true",
        "remark": os.getenv(f"REMARK_{i}", "YXIP"),
    }

    # 检查是否启用IPv4
    ipv4_enabled = os.getenv(f"IPV4_ENABLED_{i}", "true").lower() == "true"
    # 检查是否启用IPv6
    ipv6_enabled = os.getenv(f"IPV6_ENABLED_{i}", "true").lower() == "true"

    # 为每个启用的记录类型创建配置
    if ipv4_enabled:
        ipv4_config = base_config.copy()
        ipv4_config["record_type"] = "A"
        DOMAINS.append(ipv4_config)

    if ipv6_enabled:
        ipv6_config = base_config.copy()
        ipv6_config["record_type"] = "AAAA"
        DOMAINS.append(ipv6_config)

    i += 1

# 如果没有配置任何域名，使用默认配置
if not DOMAINS:
    base_config = {
        "domain": os.getenv("DOMAIN", "example.com"),
        "sub_domain": os.getenv("SUB_DOMAIN", "@"),
        "line": LINE_TYPES,
        "ttl": int(os.getenv("TTL", str(DEFAULT_TTL))),
        "update_interval": int(
            os.getenv("UPDATE_INTERVAL", str(DEFAULT_UPDATE_INTERVAL))
        ),
        "enabled": True,
    }

    # 检查默认的IPv4和IPv6设置
    ipv4_enabled = os.getenv("IPV4_ENABLED", "true").lower() == "true"
    ipv6_enabled = os.getenv("IPV6_ENABLED", "true").lower() == "true"

    if ipv4_enabled:
        ipv4_config = base_config.copy()
        ipv4_config["record_type"] = "A"
        DOMAINS.append(ipv4_config)

    if ipv6_enabled:
        ipv6_config = base_config.copy()
        ipv6_config["record_type"] = "AAAA"
        DOMAINS.append(ipv6_config)

# 日志配置
LOG_LEVEL = "INFO"
