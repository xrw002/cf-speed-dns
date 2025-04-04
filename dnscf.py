import requests
import traceback
import time
import os
import json
import re
import logging

# 初始化日志
logging.basicConfig(level=logging.INFO)

# 检查环境变量
required_envs = ["CF_API_TOKEN", "CF_ZONE_ID", "CF_DNS_NAME", "PUSHPLUS_TOKEN"]
for env in required_envs:
    if env not in os.environ:
        raise ValueError(f"Environment variable {env} is missing!")

# 配置参数
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_ZONE_ID = os.environ["CF_ZONE_ID"]
CF_DNS_NAME = os.environ["CF_DNS_NAME"]
PUSHPLUS_TOKEN = os.environ["PUSHPLUS_TOKEN"]

headers = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def is_valid_ip(ip):
    """检查 IP 地址是否合法"""
    return re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) is not None

def get_cf_speed_test_ip(timeout=10, max_retries=5):
    """获取优选 IP 列表"""
    for attempt in range(max_retries):
        try:
            response = requests.get('https://ip.164746.xyz/ipTop10.html', timeout=timeout)
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            logging.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(1)
    return None

def get_dns_records(name):
    """获取 DNS 记录 ID"""
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [record['id'] for record in response.json()['result'] if record['name'] == name]
    else:
        logging.error(f"Failed to fetch DNS records: {response.text}")
        return []

def update_dns_record(record_id, name, ip, max_retries=3):
    """更新 DNS 记录"""
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': ip
    }
    for attempt in range(max_retries):
        try:
            response = requests.put(url, headers=headers, json=data)
            if response.status_code == 200:
                logging.info(f"Updated {name} to {ip}")
                return True
            else:
                logging.error(f"Cloudflare API error: {response.text}")
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(1)
    return False

def push_plus(content):
    """推送通知"""
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "Cloudflare DNS 更新通知",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code != 200:
            logging.error(f"PushPlus 推送失败: {response.text}")
    except Exception as e:
        logging.error(f"PushPlus 请求异常: {e}")

def main():
    # 获取优选 IP
    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        push_plus("⚠️ 获取优选 IP 失败")
        return

    ip_addresses = [ip.strip() for ip in ip_addresses_str.split(',') if is_valid_ip(ip.strip())]
    if not ip_addresses:
        push_plus("⚠️ 未获取到有效 IP 地址")
        return

    # 获取 DNS 记录
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        push_plus("⚠️ 未找到匹配的 DNS 记录")
        return

    # 更新记录（按最小数量处理）
    results = []
    min_len = min(len(ip_addresses), len(dns_records))
    for i in range(min_len):
        success = update_dns_record(dns_records[i], CF_DNS_NAME, ip_addresses[i])
        results.append(f"{'✅' if success else '❌'} {CF_DNS_NAME} → {ip_addresses[i]}")

    # 推送结果
    push_plus("\n".join(results))

if __name__ == '__main__':
    main()
