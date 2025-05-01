# IPTV Web客户端

一个基于Flask的IPTV网页客户端，允许用户通过浏览器观看IPTV频道。支持导入M3U/M3U8播放列表，测试频道可用性，并提供友好的用户界面进行频道管理和观看。

![IPTV Web客户端截图](https://raw.githubusercontent.com/shnulaa/openhandTest/refs/heads/main/iptv.png)

## 功能特点

- **播放列表管理**
  - 导入M3U/M3U8播放列表文件
  - 从URL导入播放列表
  - 手动添加、编辑和删除频道
  - 批量删除频道（按分组、按状态）

- **频道组织**
  - 按分组显示频道
  - 筛选频道（全部、在线、离线、错误、未测试）
  - 支持频道状态标记（在线、离线、错误、未测试）

- **频道测试**
  - 导入时测试频道可用性
  - 测试现有频道是否可访问
  - 显示测试结果统计

- **播放功能**
  - 支持HLS流媒体播放
  - HTTP代理功能，解决混合内容问题
  - 响应式设计，适配各种设备

## 技术栈

- **后端**: Python, Flask
- **前端**: HTML, CSS, JavaScript, Bootstrap 5
- **视频播放**: HLS.js
- **容器化**: Docker, Docker Compose

## 快速开始

### 使用Docker（推荐）

1. 克隆仓库
```bash
git clone https://github.com/shnulaa/iptv-web-client.git
cd iptv-web-client
```

2. 使用Docker Compose启动应用
```bash
docker-compose up -d
```

3. 在浏览器中访问 `http://localhost:12000`

### 手动安装

1. 克隆仓库
```bash
git clone https://github.com/shnulaa/iptv-web-client.git
cd iptv-web-client
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行应用
```bash
python app.py
```

4. 在浏览器中访问 `http://localhost:12000`

## 详细使用指南

### 导入播放列表

#### 从文件导入
1. 点击导航栏中的"上传播放列表"
2. 选择本地M3U/M3U8文件
3. 点击"上传"按钮

#### 从URL导入
1. 点击导航栏中的"从URL导入"
2. 输入播放列表URL
3. 可选：勾选"测试频道是否可访问"
4. 点击"导入"按钮

### 测试频道可用性

1. 点击导航栏中的"测试频道"
2. 选择要测试的频道分组（或"所有频道"）
3. 点击"开始测试"按钮
4. 等待测试完成，查看测试结果

### 筛选和管理频道

#### 筛选频道
1. 在频道列表页面，点击"筛选"按钮
2. 选择要显示的频道状态（所有、在线、离线、错误或未测试）

#### 批量删除频道
1. 在频道列表页面，点击"删除所有频道"按钮旁边的下拉菜单
2. 选择"删除所有离线频道"或"删除所有错误频道"，或选择特定分组进行删除

### 播放频道

1. 在频道列表中点击频道卡片上的"播放"按钮
2. 使用播放器控制栏控制播放
3. 使用"上一个"和"下一个"按钮切换频道

## Docker部署

### 使用Docker Compose

项目包含了`docker-compose.yml`文件，可以轻松部署：

```bash
# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 手动构建Docker镜像

```bash
# 构建镜像
docker build -t iptv-web-client .

# 运行容器
docker run -d -p 12000:12000 -v $(pwd)/channels.json:/app/channels.json -v $(pwd)/uploads:/app/uploads --name iptv-web-client iptv-web-client
```

### 环境变量

可以通过环境变量自定义应用程序配置：

- `FLASK_APP`: Flask应用入口点（默认：app.py）
- `FLASK_ENV`: Flask环境（默认：production）
- `PORT`: 应用程序端口（默认：12000）

## 注意事项

- 支持大多数IPTV流媒体格式，包括HLS(.m3u8)
- HTTP代理功能可以解决HTTPS页面加载HTTP内容的混合内容问题
- 频道测试功能可能需要较长时间，取决于频道数量和网络状况
- 播放质量取决于您的网络连接和服务器带宽

## 贡献

欢迎提交Pull Request或Issue来帮助改进这个项目。

## 许可证

MIT
