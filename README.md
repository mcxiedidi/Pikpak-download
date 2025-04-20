# Pikpak Download Tool

一个用于下载 PikPak 网盘文件的 Python 工具。

## 功能特点

- 支持登录 PikPak 账号
- 支持批量离线下载番剧

## 使用方法

1. 安装依赖包
   ```bash
   pip install -r requirements.txt
   ```

2. 配置账号信息
   - 首次使用打开程序后填入账号密码自动生成`config.yml`
   - 在 `config.yml` 中填入 PikPak 账号和密码

3. 运行程序
   ```bash
   python main.py
   ```

4. 使用说明
   - 首次运行会要求登录验证
   - 在命令行输入您的`https://mikanime.tv/`的rss订阅链接
   - 系统自动识别对应的bt进行下载

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=mcxiedidi/Pikpak-download&type=Date)](https://www.star-history.com/#mcxiedidi/Pikpak-download&Date)
