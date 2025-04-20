# Pikpak Download Tool

一个用于下载 PikPak 网盘文件的 Python 工具。

## 功能特点

- 支持登录 PikPak 账号
- 支持批量下载文件
- 支持断点续传
- 支持下载进度显示
- 支持自定义下载路径

## 使用方法

1. 安装依赖包
   ```bash
   pip install -r requirements.txt
   ```

2. 配置账号信息
   - 复制 `config.example.yml` 为 `config.yml`
   - 在 `config.yml` 中填入 PikPak 账号和密码

3. 运行程序
   ```bash
   python main.py
   ```

4. 使用说明
   - 首次运行会要求登录验证
   - 在命令行中输入要下载的文件链接
   - 支持批量下载，每行一个链接
   - 下载完成后文件保存在 downloads 目录
