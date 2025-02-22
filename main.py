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
import subprocess
import os
from datetime import datetime, timedelta

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
        # 记录当前使用的IP
        self.current_ips = (
            {}
        )  # 格式: {domain: {'默认': {'A': ip, 'AAAA': ip}, '移动': {...}}}
        # IP可用性缓存，格式：{ip: {'available': bool, 'last_check': datetime}}
        self.ip_availability_cache = {}
        # IP可用性缓存时间设置为检查间隔的1/3
        self.cache_duration = max(1, config.check_interval // 3)
        # 初始化时获取所有域名当前的记录
        self.init_current_records()

    def init_current_records(self):
        """初始化时获取所有域名当前的解析记录"""
        logger.info("正在获取所有域名当前的解析记录...")
        for domain_config in config.DOMAINS:
            if not domain_config["enabled"]:
                continue

            domain = domain_config["domain"]
            sub_domain = domain_config["sub_domain"]

            # 获取当前记录
            current_records = self.get_current_records(domain, sub_domain)
            if current_records:
                self.current_ips[domain] = current_records
                logger.info(f"域名 {domain} - {sub_domain} 当前记录：")
                for line, records in current_records.items():
                    for record_type, ip in records.items():
                        logger.info(f"  - {line} - {record_type}: {ip}")
            else:
                logger.warning(f"域名 {domain} - {sub_domain} 暂无解析记录")

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

    def get_current_records(self, domain: str, sub_domain: str) -> Dict:
        """获取当前域名的所有记录"""
        try:
            records = self.get_record_list(domain, sub_domain)
            current_records = {}
            for record in records:
                if record.Line not in current_records:
                    current_records[record.Line] = {}
                current_records[record.Line][record.Type] = record.Value
            return current_records
        except Exception as e:
            logger.error(f"获取当前记录失败: {str(e)}")
            return {}

    def check_ip_availability(self, ip: str) -> bool:
        """检查IP是否可以ping通"""
        # 检查缓存
        now = datetime.now()
        if ip in self.ip_availability_cache:
            cache_info = self.ip_availability_cache[ip]
            if now - cache_info['last_check'] < timedelta(minutes=self.cache_duration):
                return cache_info['available']

        try:
            # 根据操作系统选择ping命令参数
            if os.name == 'nt':  # Windows系统
                ping_args = ['ping', '-n', '1', '-w', '1000', ip]
            else:  # Linux/Unix系统
                ping_args = ['ping', '-c', '1', '-W', '1', ip]
            
            result = subprocess.run(ping_args, 
                                  capture_output=True, 
                                  text=True)
            available = result.returncode == 0
            
            # 更新缓存
            self.ip_availability_cache[ip] = {
                'available': available,
                'last_check': now
            }
            
            if not available:
                logger.warning(f"IP {ip} ping测试失败，命令输出：{result.stdout if result.stdout else result.stderr}")
            return available
        except Exception as e:
            logger.error(f"Ping测试出错 - IP: {ip}, 错误信息: {str(e)}, 命令参数: {ping_args}")
            return False

    def find_best_available_ip(self, ip_data: Dict, ip_version: str) -> Optional[Tuple[str, int]]:
        """查找可用且延迟最低的IP，返回(IP, 延迟)"""
        if ip_version != "v4":  # 只检查IPv4地址
            return self.find_best_ip(ip_data, ip_version)

        # 按延迟排序所有IP地址，并获取优选IP，检查IP可用性，更新不同线路的记录等功能。
        all_ips = []
        for line_key in ["CM", "CU", "CT"]:
            if line_key in ip_data[ip_version]:
                all_ips.extend(ip_data[ip_version][line_key])
        
        # 按延迟排序
        all_ips.sort(key=lambda x: x["latency"])
        
        # 查找第一个可用的IP
        for ip_info in all_ips:
            if self.check_ip_availability(ip_info["ip"]):
                return (ip_info["ip"], ip_info["latency"])
        
        return None

    def find_line_best_available_ip(
        self, ip_data: Dict, ip_version: str, line_key: str
    ) -> Optional[Tuple[str, int]]:
        """查找指定线路可用且延迟最低的IP"""
        if ip_version != "v4":  # 只检查IPv4地址
            return self.find_line_best_ip(ip_data, ip_version, line_key)

        if line_key not in ip_data[ip_version]:
            return None

        ips = ip_data[ip_version][line_key]
        if not ips:
            return None

        # 按延迟排序
        ips.sort(key=lambda x: x["latency"])
        
        # 查找第一个可用的IP
        for ip_info in ips:
            if self.check_ip_availability(ip_info["ip"]):
                return (ip_info["ip"], ip_info["latency"])
        
        return None
    def update_domain_records(self, domain_config):
        """更新指定域名的记录"""
        domain = domain_config["domain"]
        sub_domain = domain_config["sub_domain"]
        ttl = domain_config.get("ttl", 600)
        remark = domain_config.get("remark")

        # 获取当前记录
        current_records = self.get_current_records(domain, sub_domain)

        # 获取优选IP
        ip_data = self.get_optimal_ips()
        if not ip_data:
            logger.error(f"无法获取优选IP，跳过更新 {domain}")
            return

        # 处理IPv4记录
        if domain_config["ipv4_enabled"] and "v4" in ip_data:
            # 获取所有线路的最佳IPv4地址
            line_mapping = {"移动": "CM", "联通": "CU", "电信": "CT"}
            best_ips = {}
            for line, line_key in line_mapping.items():
                best_ip = self.find_line_best_available_ip(ip_data, "v4", line_key)
                if best_ip:
                    ip, latency = best_ip
                    best_ips[line] = (ip, latency)

            # 检查是否所有线路的IPv4地址都相同
            if best_ips:
                unique_ips = {ip for ip, _ in best_ips.values()}
                if len(unique_ips) == 1:
                    # 所有线路的IPv4地址相同，只添加默认线路
                    ip = list(unique_ips)[0]
                    min_latency = min(latency for _, latency in best_ips.values())
                    current_ip = current_records.get("默认", {}).get("A")
                    if current_ip != ip:
                        logger.info(
                            f"更新A记录: {domain} - {sub_domain} - 默认 - {ip} (延迟: {min_latency}ms) [所有线路IP相同]"
                        )
                        if self.update_record(
                            domain, sub_domain, "A", "默认", ip, ttl, remark
                        ):
                            # 更新成功后更新缓存
                            if "默认" not in current_records:
                                current_records["默认"] = {}
                            current_records["默认"]["A"] = ip
                        time.sleep(1)
                else:
                    # IPv4地址不同，需要为每个线路添加记录
                    for line, (ip, latency) in best_ips.items():
                        current_ip = current_records.get(line, {}).get("A")
                        if current_ip != ip:
                            logger.info(
                                f"更新A记录: {domain} - {sub_domain} - {line} - {ip} (延迟: {latency}ms)"
                            )
                            if self.update_record(
                                domain, sub_domain, "A", line, ip, ttl, remark
                            ):
                                # 更新成功后更新缓存
                                if line not in current_records:
                                    current_records[line] = {}
                                current_records[line]["A"] = ip
                            time.sleep(1)

                    # 添加默认线路（使用延迟最低的IP）
                    best_ip = min(best_ips.items(), key=lambda x: x[1][1])
                    ip, latency = best_ip[1]
                    current_ip = current_records.get("默认", {}).get("A")
                    if current_ip != ip:
                        logger.info(
                            f"更新A记录: {domain} - {sub_domain} - 默认 - {ip} (延迟: {latency}ms)"
                        )
                        if self.update_record(
                            domain, sub_domain, "A", "默认", ip, ttl, remark
                        ):
                            # 更新成功后更新缓存
                            if "默认" not in current_records:
                                current_records["默认"] = {}
                            current_records["默认"]["A"] = ip
                        time.sleep(1)

        # 处理IPv6记录
        if domain_config["ipv6_enabled"] and "v6" in ip_data:
            # 获取所有线路的最佳IPv6地址
            line_mapping = {"移动": "CM", "联通": "CU", "电信": "CT"}
            best_ips = {}
            for line, line_key in line_mapping.items():
                best_ip = self.find_line_best_ip(ip_data, "v6", line_key)
                if best_ip:
                    ip, latency = best_ip
                    best_ips[line] = (ip, latency)

            # 检查是否所有线路的IPv6地址都相同
            if best_ips:
                unique_ips = {ip for ip, _ in best_ips.values()}
                if len(unique_ips) == 1:
                    # 所有线路的IPv6地址相同，只添加默认线路
                    ip = list(unique_ips)[0]
                    min_latency = min(latency for _, latency in best_ips.values())
                    current_ip = current_records.get("默认", {}).get("AAAA")
                    if current_ip != ip:
                        logger.info(
                            f"更新AAAA记录: {domain} - {sub_domain} - 默认 - {ip} (延迟: {min_latency}ms) [所有线路IP相同]"
                        )
                        if self.update_record(
                            domain, sub_domain, "AAAA", "默认", ip, ttl, remark
                        ):
                            # 更新成功后更新缓存
                            if "默认" not in current_records:
                                current_records["默认"] = {}
                            current_records["默认"]["AAAA"] = ip
                        time.sleep(1)
                else:
                    # IPv6地址不同，需要为每个线路添加记录
                    for line, (ip, latency) in best_ips.items():
                        current_ip = current_records.get(line, {}).get("AAAA")
                        if current_ip != ip:
                            logger.info(
                                f"更新AAAA记录: {domain} - {sub_domain} - {line} - {ip} (延迟: {latency}ms)"
                            )
                            if self.update_record(
                                domain, sub_domain, "AAAA", line, ip, ttl, remark
                            ):
                                # 更新成功后更新缓存
                                if line not in current_records:
                                    current_records[line] = {}
                                current_records[line]["AAAA"] = ip
                            time.sleep(1)

                    # 添加默认线路（使用延迟最低的IP）
                    best_ip = min(best_ips.items(), key=lambda x: x[1][1])
                    ip, latency = best_ip[1]
                    current_ip = current_records.get("默认", {}).get("AAAA")
                    if current_ip != ip:
                        logger.info(
                            f"更新AAAA记录: {domain} - {sub_domain} - 默认 - {ip} (延迟: {latency}ms)"
                        )
                        if self.update_record(
                            domain, sub_domain, "AAAA", "默认", ip, ttl, remark
                        ):
                            # 更新成功后更新缓存
                            if "默认" not in current_records:
                                current_records["默认"] = {}
                            current_records["默认"]["AAAA"] = ip
                        time.sleep(1)

    def check_and_update(self):
        """检查并更新所有域名"""
        for domain_config in config.DOMAINS:
            if not domain_config["enabled"]:
                continue
            self.update_domain_records(domain_config)
            time.sleep(1)  # 添加延时


def main():
    manager = DNSPodManager()

    # 首次运行，更新所有域名
    manager.check_and_update()

    # 每5分钟检查一次是否需要更新
    schedule.every(config.check_interval).minutes.do(manager.check_and_update)
    logger.info(f"程序启动成功，开始监控更新（每{config.check_interval}分钟检查一次）...")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
