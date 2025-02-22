import os
from typing import Dict, List
import yaml

# 加载YAML配置
def load_config() -> Dict:
    """从YAML文件加载配置"""
    yaml_files = ["config.yaml", "config.example.yaml"]
    for yaml_file in yaml_files:
        if os.path.exists(yaml_file):
            with open(yaml_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    return {}

# 加载配置
config_data = load_config()

# 腾讯云API配置
SECRET_ID = config_data.get("tencent", {}).get("secret_id")
SECRET_KEY = config_data.get("tencent", {}).get("secret_key")

# API接口配置
API_URL = "https://api.vvhan.com/tool/cf_ip"

# 日志级别
LOG_LEVEL = config_data.get("log_level", "INFO")

# 更新检查间隔（分钟）
check_interval = config_data.get("check_interval", 15)

# 获取所有域名配置
DOMAINS = config_data.get("domains", [])
