import json
import time
import requests
import schedule
from loguru import logger
from typing import Dict, List, Optional, Tuple
import config
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.dnspod.v20210323 import dnspod_client, models

# 配置日志
logger.add("logs/dnspod.log", rotation="10 MB", level=config.LOG_LEVEL)


class DNSPodManager:
    def __init__(self):
        # 实例化一个认证对象
        cred = credential.Credential(config.SECRET_ID, config.SECRET_KEY)
        # 实例化一个http选项，可选的，没有特殊需求可以跳过
        httpProfile = HttpProfile()
        httpProfile.endpoint = "dnspod.tencentcloudapi.com"
        # 实例化一个client选项，可选的，没有特殊需求可以跳过
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        # 实例化要请求产品的client对象
        self.client = dnspod_client.DnspodClient(cred, "", clientProfile)
        # 记录每个域名每种记录类型的最后更新时间
        self.last_update = {}  # 格式: {domain: {'A': timestamp, 'AAAA': timestamp}}

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

    def get_record_list(
        self, domain: str, sub_domain: str = None, record_type: str = None
    ) -> List:
        """获取域名记录列表"""
        try:
            # 实例化一个请求对象
            req = models.DescribeRecordListRequest()
            req.Domain = domain
            if sub_domain:
                req.Subdomain = sub_domain
            if record_type:
                req.RecordType = record_type

            # 通过client对象调用DescribeRecordList接口
            resp = self.client.DescribeRecordList(req)
            return resp.RecordList
        except Exception as e:
            logger.error(f"获取记录列表失败: {str(e)}")
            return []

    def delete_record(self, domain: str, record_id: int) -> bool:
        """删除DNS记录"""
        try:
            req = models.DeleteRecordRequest()
            req.Domain = domain
            req.RecordId = record_id
            self.client.DeleteRecord(req)
            return True
        except Exception as e:
            logger.error(f"删除记录失败: {str(e)}")
            return False

    def clean_existing_records(
        self, domain: str, sub_domain: str, record_type: str, line: str
    ) -> None:
        """清理指定类型和线路的现有记录"""
        try:
            # 定义我们要管理的线路
            managed_lines = ["默认", "移动", "联通", "电信"]

            # 如果不是我们管理的线路，直接返回
            if line not in managed_lines:
                return

            records = self.get_record_list(domain, sub_domain, record_type)
            for record in records:
                # 只删除我们管理的线路中的记录
                if record.Line == line and record.Line in managed_lines:
                    logger.info(
                        f"删除旧记录: {domain} - {sub_domain} - {line} - {record.Value}"
                    )
                    self.delete_record(domain, record.RecordId)
                    time.sleep(1)  # 添加短暂延时
        except Exception as e:
            logger.error(f"清理记录时出错: {str(e)}")

    def update_record(
        self,
        domain: str,
        sub_domain: str,
        record_type: str,
        line: str,
        value: str,
        ttl: int,
        remark: str = None,
    ) -> bool:
        """更新或创建DNS记录"""
        try:
            # 先清理现有记录
            self.clean_existing_records(domain, sub_domain, record_type, line)
            time.sleep(1)  # 添加短暂延时

            # 创建新记录
            req = models.CreateRecordRequest()
            req.Domain = domain
            req.SubDomain = sub_domain
            req.RecordType = record_type
            req.RecordLine = line
            req.Value = value
            req.TTL = ttl
            if remark:
                req.Remark = remark

            self.client.CreateRecord(req)
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
            success = self.update_record(
                domain, sub_domain, record_type, "默认", ip, ttl, remark
            )
            if not success:
                logger.error(f"更新默认线路记录失败: {domain} - {sub_domain}")
            time.sleep(1)  # 添加延时

        # 更新其他线路的记录
        line_mapping = {"移动": "CM", "联通": "CU", "电信": "CT"}

        for line, line_key in line_mapping.items():
            if line_key in ip_data[ip_version] and ip_data[ip_version][line_key]:
                best_ip = self.find_line_best_ip(ip_data, ip_version, line_key)
                if best_ip:
                    ip, latency = best_ip
                    logger.info(
                        f"更新{record_type}记录: {domain} - {sub_domain} - {line} - {ip} (延迟: {latency}ms)"
                    )
                    success = self.update_record(
                        domain, sub_domain, record_type, line, ip, ttl, remark
                    )
                    if not success:
                        logger.error(f"更新{line}线路记录失败: {domain} - {sub_domain}")
                    time.sleep(1)  # 添加延时

    def check_and_update(self):
        """检查并更新所有域名"""
        current_time = time.time()

        for domain_config in config.DOMAINS:
            if not domain_config["enabled"]:
                continue

            domain = domain_config["domain"]

            # 处理IPv4记录
            if domain_config["ipv4_enabled"]:
                ipv4_config = domain_config.copy()
                ipv4_config["record_type"] = "A"
                self.update_domain_records(ipv4_config)
                time.sleep(1)  # 添加延时

            # 处理IPv6记录
            if domain_config["ipv6_enabled"]:
                ipv6_config = domain_config.copy()
                ipv6_config["record_type"] = "AAAA"
                self.update_domain_records(ipv6_config)
                time.sleep(1)  # 添加延时


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
