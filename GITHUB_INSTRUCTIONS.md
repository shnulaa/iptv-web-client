# 将IPTV Web客户端推送到GitHub的说明

按照以下步骤将IPTV Web客户端代码推送到您的GitHub仓库：

## 1. 创建GitHub仓库

1. 登录您的GitHub账户
2. 点击右上角的"+"图标，然后选择"New repository"
3. 填写仓库名称，例如"iptv-web-client"
4. 添加描述："一个基于Flask的IPTV网页客户端，允许用户通过浏览器观看IPTV频道"
5. 选择公开或私有仓库
6. 不要初始化仓库（不要添加README、.gitignore或许可证）
7. 点击"Create repository"

## 2. 推送代码到GitHub

在您的本地终端中执行以下命令：

```bash
# 进入项目目录
cd /path/to/iptv-web-client

# 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/iptv-web-client.git

# 推送代码到GitHub
git push -u origin main
```

请将`YOUR_USERNAME`替换为您的GitHub用户名。

## 3. 验证推送

1. 访问您的GitHub仓库页面：`https://github.com/YOUR_USERNAME/iptv-web-client`
2. 确认所有文件都已成功推送

## 4. 启用GitHub Pages（可选）

如果您想通过GitHub Pages展示项目文档：

1. 在仓库页面，点击"Settings"
2. 滚动到"GitHub Pages"部分
3. 在"Source"下拉菜单中选择"main"分支
4. 点击"Save"
5. 页面刷新后，您将看到GitHub Pages的URL

## 5. 创建Release（可选）

1. 在仓库页面，点击"Releases"
2. 点击"Create a new release"
3. 输入版本号，例如"v1.0.0"
4. 添加发布标题和描述
5. 点击"Publish release"

现在，您的IPTV Web客户端已成功发布到GitHub，其他人可以克隆、使用和贡献代码。