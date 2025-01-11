import json
import time
import requests
import schedule
from loguru import logger
from typing import Dict, List, Optional, Tuple
import config

# 配置日志
logger.add("dnspod.log", rotation="10 MB", level=config.LOG_LEVEL)


class DNSPodManager:
    def __init__(self):
        self.api_url = "https://dnsapi.cn"
        self.common_params = {
            "login_token": f"{config.DNSPOD_ID},{config.DNSPOD_TOKEN}",
            "format": "json",
            "lang": "cn",
            "error_on_empty": "no",
        }
        # 记录每个域名每种记录类型的最后更新时间
        self.last_update = {}  # 格式: {domain: {'A': timestamp, 'AAAA': timestamp}}

    def _api_request(self, path: str, data: Dict) -> Dict:
        """发送API请求"""
        try:
            url = f"{self.api_url}/{path}"
            response = requests.post(url, data={**self.common_params, **data})
            result = response.json()

            if int(result.get("status", {}).get("code", -1)) != 1:
                raise Exception(result.get("status", {}).get("message", "未知错误"))

            return result
        except Exception as e:
            logger.error(f"API请求失败: {str(e)}")
            raise

    def get_optimal_ips(self) -> Dict:
        """获取优选IP"""
        try:
            response = requests.get(config.API_URL)
            data = response.json()
            if data.get("success"):
                return data["data"]
            raise Exception("API返回数据格式错误")
        except Exception as e:
            logger.error(f"获取优选IP失败: {str(e)}")
            return None

    def find_best_ip(self, ip_data: Dict, ip_version: str) -> Optional[Tuple[str, int]]:
        """查找延迟最低的IP，返回(IP, 延迟)"""
        best_ip = None
        min_latency = float("inf")

        # 遍历所有线路
        for line_key in ["CM", "CU", "CT"]:
            if line_key in ip_data[ip_version]:
                ips = ip_data[ip_version][line_key]
                for ip_info in ips:
                    if ip_info["latency"] < min_latency:
                        min_latency = ip_info["latency"]
                        best_ip = (ip_info["ip"], ip_info["latency"])

        return best_ip

    def find_line_best_ip(
        self, ip_data: Dict, ip_version: str, line_key: str
    ) -> Optional[Tuple[str, int]]:
        """查找指定线路延迟最低的IP"""
        if line_key not in ip_data[ip_version]:
            return None

        ips = ip_data[ip_version][line_key]
        if not ips:
            return None

        best_ip = min(ips, key=lambda x: x["latency"])
        return (best_ip["ip"], best_ip["latency"])

    def get_record_list(self, domain: str) -> List:
        """获取域名记录列表"""
        try:
            result = self._api_request("Record.List", {"domain": domain})
            return result.get("records", [])
        except Exception as e:
            logger.error(f"获取记录列表失败: {str(e)}")
            return []

    def delete_record(self, domain: str, record_id: str) -> bool:
        """删除DNS记录"""
        try:
            self._api_request(
                "Record.Remove", {"domain": domain, "record_id": record_id}
            )
            return True
        except Exception as e:
            logger.error(f"删除记录失败: {str(e)}")
            return False

    def handle_record_conflicts(self, domain: str, sub_domain: str, record_type: str):
        """处理记录冲突"""
        records = self.get_record_list(domain)
        for record in records:
            # 如果是要添加A记录，需要删除CNAME记录
            if (
                record_type == "A"
                and record["type"] == "CNAME"
                and record["name"] == sub_domain
            ):
                logger.info(f"删除冲突的CNAME记录: {domain} - {sub_domain}")
                self.delete_record(domain, record["id"])
            # 如果是要添加CNAME记录，需要删除A记录
            elif (
                record_type == "CNAME"
                and record["type"] == "A"
                and record["name"] == sub_domain
            ):
                logger.info(f"删除冲突的A记录: {domain} - {sub_domain}")
                self.delete_record(domain, record["id"])

    def update_record(
        self,
        domain: str,
        sub_domain: str,
        record_type: str,
        line: str,
        value: str,
        ttl: int,
        remark: str = "YXIP",
    ) -> bool:
        """更新DNS记录"""
        try:
            # 处理记录冲突
            self.handle_record_conflicts(domain, sub_domain, record_type)

            # 获取域名记录列表
            records = self.get_record_list(domain)

            # 查找匹配的记录
            record_id = None
            for record in records:
                if (
                    record["name"] == sub_domain
                    and record["line"] == line
                    and record["type"] == record_type
                ):
                    record_id = record["id"]
                    break

            # 更新或创建记录
            data = {
                "domain": domain,
                "sub_domain": sub_domain,
                "record_type": record_type,
                "record_line": line,
                "value": value,
                "ttl": ttl,
                "remark": remark,
            }

            if record_id:
                data["record_id"] = record_id
                self._api_request("Record.Modify", data)
            else:
                self._api_request("Record.Create", data)
            return True
        except Exception as e:
            logger.error(f"更新DNS记录失败: {str(e)}")
            return False

    def update_domain_records(self, domain_config: Dict) -> None:
        """更新单个域名的记录"""
        domain = domain_config["domain"]
        sub_domain = domain_config["sub_domain"]
        record_type = domain_config["record_type"]
        ttl = domain_config["ttl"]
        remark = domain_config["remark"]

        # 获取优选IP数据
        ip_data = self.get_optimal_ips()
        if not ip_data:
            return

        # 获取对应版本的IP数据
        ip_version = "v6" if record_type == "AAAA" else "v4"
        if ip_version not in ip_data:
            logger.warning(
                f"未找到{ip_version}版本的IP数据，跳过更新 {domain} 的 {record_type} 记录"
            )
            return

        # 检查是否有可用的IP数据
        has_ip_data = False
        for line_key in ["CM", "CU", "CT"]:
            if line_key in ip_data[ip_version] and ip_data[ip_version][line_key]:
                has_ip_data = True
                break

        if not has_ip_data:
            logger.warning(
                f"没有可用的{ip_version}版本IP数据，跳过更新 {domain} 的 {record_type} 记录"
            )
            return

        # 先处理默认线路
        best_ip = self.find_best_ip(ip_data, ip_version)
        if best_ip:
            ip, latency = best_ip
            logger.info(
                f"更新{record_type}记录: {domain} - {sub_domain} - 默认 - {ip} (延迟: {latency}ms)"
            )
            self.update_record(domain, sub_domain, record_type, "默认", ip, ttl, remark)

        # 更新其他线路的记录
        for line in domain_config["line"]:
            if line == "默认":
                continue

            if line == "移动":
                line_key = "CM"
            elif line == "联通":
                line_key = "CU"
            elif line == "电信":
                line_key = "CT"
            else:
                continue

            if line_key in ip_data[ip_version]:
                best_ip = self.find_line_best_ip(ip_data, ip_version, line_key)
                if best_ip:
                    ip, latency = best_ip
                    logger.info(
                        f"更新{record_type}记录: {domain} - {sub_domain} - {line} - {ip} (延迟: {latency}ms)"
                    )
                    self.update_record(
                        domain, sub_domain, record_type, line, ip, ttl, remark
                    )

    def check_and_update(self):
        """检查并更新所有域名"""
        current_time = time.time()

        for domain_config in config.DOMAINS:
            if not domain_config["enabled"]:
                continue

            domain = domain_config["domain"]
            record_type = domain_config["record_type"]
            update_interval = domain_config["update_interval"] * 60  # 转换为秒

            # 初始化域名的更新时间记录
            if domain not in self.last_update:
                self.last_update[domain] = {}

            # 获取该记录类型的最后更新时间
            last_update = self.last_update[domain].get(record_type, 0)

            # 检查是否需要更新
            if current_time - last_update >= update_interval:
                logger.info(f"开始更新域名: {domain} 的 {record_type} 记录")
                self.update_domain_records(domain_config)
                self.last_update[domain][record_type] = current_time


def main():
    manager = DNSPodManager()

    # 首次运行，更新所有域名
    manager.check_and_update()

    # 每分钟检查一次是否需要更新
    schedule.every(1).minutes.do(manager.check_and_update)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
