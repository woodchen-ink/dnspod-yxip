# DNSPOD 优选域名

根据API接口返回的IP地址, 在DNSPOD中创建或者更新域名的解析记录, 支持分线路和多权重。 

支持docker运行, 需要配置DNSPOD的ID和TOKEN, 可以配置多个域名。默认每15分钟自动获取IP地址并更新DNSPOD。

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
cp .env.example .env
```

2. 编辑 `.env` 文件，填写您的配置：
```ini
# DNSPOD API 配置
DNSPOD_ID=your_id_here
DNSPOD_TOKEN=your_token_here

# 域名配置 - 域名1
DOMAIN_1=example1.com
SUB_DOMAIN_1=@           # 子域名，@ 表示根域名
REMARK_1=优选IP          # 记录备注
TTL_1=600               # TTL值（秒）
UPDATE_INTERVAL_1=15     # 更新间隔（分钟）
IPV4_ENABLED_1=true     # 是否启用IPv4记录
IPV6_ENABLED_1=true     # 是否启用IPv6记录
ENABLED_1=true          # 是否启用此域名配置
```

3. 拉取并运行容器：
```bash
docker compose pull
docker compose up -d
```

### 手动构建运行

1. 克隆仓库：
```bash
git clone https://github.com/your-username/dnspod-yxip.git
cd dnspod-yxip
```

2. 创建并编辑配置文件：
```bash
cp .env.example .env
# 编辑 .env 文件
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
- `DOMAIN_n`: 域名
- `SUB_DOMAIN_n`: 子域名，@ 表示根域名，* 表示泛解析
- `REMARK_n`: 记录备注
- `TTL_n`: TTL值（秒）
- `UPDATE_INTERVAL_n`: 更新间隔（分钟）
- `IPV4_ENABLED_n`: 是否启用IPv4记录
- `IPV6_ENABLED_n`: 是否启用IPv6记录
- `ENABLED_n`: 是否启用此域名配置

其中 n 是域名编号（1, 2, 3...），可以配置任意数量的域名。

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
