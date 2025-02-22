# DNSPOD 优选域名

> 主要针对根域名的CNAME解析和MX解析的冲突问题, 二级域名可以直接指向 **.cf.cname.vvhan.com, 参考网站: https://cf.vvhan.com/  
> 感谢 https://cf.vvhan.com/ 提供的API接口

根据API接口返回的IP地址, 在DNSPOD中创建或者更新域名的解析记录, 自动创建 默认, 联通, 电信, 移动 四个线路的解析记录。 

支持docker运行, 需要配置腾讯云的密钥, 可以配置多个域名。5分钟请求一次接口, 并进行对比。

## 效果

![image](https://github.com/user-attachments/assets/b334e833-417a-4919-ae7c-799de67e60ba)


## 特性

- 自动获取优选IP地址
- 支持IPv4和IPv6
- 支持移动、联通、电信三个线路
- 自动选择延迟最低的IP
- 支持多域名配置
- 可配置的更新间隔和TTL
- 完整的日志记录
- Docker支持

## 快速开始

### 使用 Docker Compose

1. 创建配置文件：
```bash
cp config.example.yaml config.yaml
```

2. 编辑 `config.yaml` 文件，填写您的配置：

3. 拉取并运行容器：
```bash
docker compose pull
docker compose up -d
```

### 手动构建运行

1. 克隆仓库：
```bash
git clone https://github.com/woodchen-ink/dnspod-yxip.git
cd dnspod-yxip
```

2. 创建并编辑配置文件：
```bash
cp config.example.yaml config.yaml
# 编辑 config 文件
```

3. 构建镜像：
```bash
docker compose build
```

4. 运行容器：
```bash
docker compose up -d
```

## 配置说明

每个域名配置包含以下参数：
- `DOMAIN`: 域名
- `SUB_DOMAIN`: 子域名，@ 表示根域名，* 表示泛解析
- `REMARK`: 记录备注
- `TTL`: TTL值（秒）
- `IPV4_ENABLED`: 是否启用IPv4记录
- `IPV6_ENABLED`: 是否启用IPv6记录
- `ENABLED`: 是否启用此域名配置


## 日志查看

日志文件保存在 `logs` 目录下：
```bash
# 查看实时日志
docker compose logs -f

# 查看日志文件
cat logs/dnspod.log
```

## 更新

1. 拉取最新镜像：
```bash
docker compose pull
```

2. 重新启动容器：
```bash
docker compose up -d
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

