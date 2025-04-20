import asyncio
import feedparser
import os
import signal
import sys
import time
import httpx
import json
from pikpakapi import PikPakApi
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.progress import Progress
import logging


CONFIG_FILE = "config.json"     # 配置文件（保存基本配置）
CLIENT_STATE_FILE = "pikpak.json"    # 客户端状态文件（保存 PikPakApi 登录状态及 token 等信息）

# 全局变量（由配置文件或手动填写）
USER = [""]
PASSWORD = [""]
PATH = [""]
RSS = [""]
INTERVAL_TIME_RSS = 600  # rss 检查间隔
INTERVAL_TIME_REFRESH = 21600  # token 刷新间隔
PIKPAK_CLIENTS = [""]
last_refresh_time = 0

# Initialize Rich Console
console = Console()


# 加载基本配置文件，并更新全局变量
def load_config():
    config_complete = False
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Check if all required keys exist and are not empty
            if config.get("username") and config.get("password") and config.get("path") and config.get("rss"):
                USER[0] = config.get("username")
                PASSWORD[0] = config.get("password")
                PATH[0] = config.get("path")
                RSS[0] = config.get("rss")
                console.log("[green]配置文件加载成功！[/green]")
                config_complete = True
            else:
                console.log("[yellow]配置文件不完整，需要补充信息。[/yellow]")
                # Load existing values or prompt if missing
                USER[0] = config.get("username") or console.input("请输入 PikPak 用户名: ")
                PASSWORD[0] = config.get("password") or console.input("请输入 PikPak 密码: ", password=True)
                PATH[0] = config.get("path") or console.input("请输入 PikPak 保存路径 (文件夹 ID): ")
                RSS[0] = config.get("rss") or console.input("请输入 RSS 订阅链接: ")
                update_config() # Save the completed config
                config_complete = True # Mark as complete after getting input
        except Exception as e:
            console.log(f"[red]加载配置文件失败: {str(e)}，将提示输入。[/red]")
            # Fall through to prompt if loading fails
    
    if not config_complete: # Prompt if file doesn't exist or loading failed/incomplete
        console.log("[yellow]配置文件不存在或加载失败，请手动输入配置信息。[/yellow]")
        USER[0] = console.input("请输入 PikPak 用户名: ")
        PASSWORD[0] = console.input("请输入 PikPak 密码: ", password=True)
        PATH[0] = console.input("请输入 PikPak 保存路径 (文件夹 ID): ")
        RSS[0] = console.input("请输入 RSS 订阅链接: ")
        update_config() # Save the newly created config


# 如果存在保存的客户端状态，则优先从 CLIENT_STATE_FILE 中加载token
# 否则根据用户名和密码新建客户端对象
# 此外，检验客户端是否是当前用户的，若不是则重新登录
def init_clients():
    global last_refresh_time
    client = None
    if os.path.exists(CLIENT_STATE_FILE):
        try:
            with open(CLIENT_STATE_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            last_refresh_time = config.get("last_refresh_time", 0)
            client_token = config.get("client_token", {})
            if client_token and client_token.get("username") == USER[0]:
                client = PikPakApi.from_dict(client_token)
                console.log("[green]成功从客户端状态文件加载登录状态！[/green]")
            else:
                console.log("[yellow]客户端状态文件中的用户名与配置不符，将重新创建客户端。[/yellow]")
                client = PikPakApi(username=USER[0], password=PASSWORD[0])
        except Exception as e:
            console.log(f"[yellow]加载客户端状态失败: {str(e)}，将尝试使用配置中的用户名/密码创建客户端。[/yellow]")
            if not USER[0] or not PASSWORD[0]:
                console.log("[red]配置中缺少用户名或密码，无法创建客户端。请检查 config.json 或环境变量。[/red]")
                client = None # Set client to None if credentials missing
            else:
                try:
                    client = PikPakApi(username=USER[0], password=PASSWORD[0])
                except Exception as api_e:
                    console.log(f"[red]使用配置创建客户端失败: {api_e}[/red]")
                    client = None
    else:
        console.log("[yellow]客户端状态文件不存在，将尝试使用配置中的用户名/密码创建新客户端。[/yellow]")
        if not USER[0] or not PASSWORD[0]:
            console.log("[red]配置中缺少用户名或密码，无法创建客户端。请检查 config.json 或环境变量。[/red]")
            client = None # Set client to None if credentials missing
        else:
            try:
                client = PikPakApi(username=USER[0], password=PASSWORD[0])
            except Exception as api_e:
                console.log(f"[red]使用配置创建客户端失败: {api_e}[/red]")
                client = None

    PIKPAK_CLIENTS[0] = client


# 保存基本配置到 CONFIG_FILE
def update_config():
    config = {
        "username": USER[0],
        "password": PASSWORD[0],
        "path": PATH[0],
        "rss": RSS[0],
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        # console.log("[green]配置文件更新成功！[/green]") # Avoid logging this every time
    except Exception as e:
        console.log(f"[red]配置文件更新失败: {str(e)}[/red]")


# 保存token到 CLIENT_STATE_FILE
def save_client():
    if not PIKPAK_CLIENTS[0]: # Avoid saving if client initialization failed
        console.log("[yellow]客户端未初始化，跳过保存状态。[/yellow]")
        return
    config = {
        "last_refresh_time": last_refresh_time,
        "client_token": PIKPAK_CLIENTS[0].to_dict(),
    }
    try:
        with open(CLIENT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        console.log("[green]客户端状态保存成功！[/green]")
    except Exception as e:
        console.log(f"[red]客户端状态保存失败: {str(e)}[/red]")


# 1. 先尝试调用 file_list() 检查 token 是否有效；
# 2. 若调用失败，则重新使用用户名密码登录；
async def login(account_index):
    client = PIKPAK_CLIENTS[account_index]
    if not client: # Check if client exists
        console.log(f"[red]账号 {account_index} 客户端未初始化，无法登录。[/red]")
        return
    try:
        # 尝试用 token 调用 file_list() 检查 token 是否有效
        await client.file_list(parent_id=PATH[account_index])
        console.log(f"账号 [cyan]{USER[account_index]}[/cyan] Token 有效")
    except Exception as e:
        console.log(f"[yellow]使用 token 读取文件列表失败: {str(e)}，将重新登录。[/yellow]")
        try:
            await client.login()
            console.log(f"账号 [cyan]{USER[account_index]}[/cyan] 登录成功！")
            save_client() # Save client state after successful login
        except Exception as e:
            console.log(f"[red]账号 {USER[account_index]} 登录失败: {str(e)}[/red]")
            PIKPAK_CLIENTS[account_index] = None # Mark client as invalid
            return

    # await auto_refresh_token() # Refresh token is handled in main loop


# 定时刷新 token
async def auto_refresh_token():
    global last_refresh_time
    current_time = time.time()
    # Check if client exists and token needs refresh
    if PIKPAK_CLIENTS[0] and (current_time - last_refresh_time >= INTERVAL_TIME_REFRESH):
        console.log("尝试刷新 token...")
        try:
            client = PIKPAK_CLIENTS[0]
            await client.refresh_access_token()
            console.log("[green]token 刷新成功！[/green]")
            last_refresh_time = current_time
            save_client()
        except Exception as e:
            console.log(f"[red]token 刷新失败: {str(e)}[/red]")
            last_refresh_time = 0 # Reset time to force login next time
            # Consider attempting relogin here or marking client as invalid
            try:
                 console.log("[yellow]尝试重新登录...[/yellow]")
                 await PIKPAK_CLIENTS[0].login()
                 console.log(f"账号 [cyan]{USER[0]}[/cyan] 重新登录成功！")
                 save_client()
            except Exception as login_e:
                 console.log(f"[red]重新登录失败: {login_e}[/red]")
                 PIKPAK_CLIENTS[0] = None # Mark client as invalid


# 解析 RSS 并返回种子列表
async def get_rss():
    console.log(f"正在解析 RSS: [link={RSS[0]}]{RSS[0]}[/link]")
    try:
        rss = feedparser.parse(RSS[0])
        if rss.bozo:
            console.log(f"[red]RSS 解析错误: {rss.bozo_exception}[/red]")
            return []
        entries = [
            {
                'title': entry.get('title', 'N/A'),
                'link': entry.get('link', 'N/A'),
                'torrent': entry.enclosures[0]['url'] if entry.get('enclosures') else 'N/A',
                'pubdate': entry.get('published', '').split("T")[0] if entry.get('published') else 'N/A'
            }
            for entry in rss.get('entries', [])
        ]
        # console.log(f"成功解析到 {len(entries)} 个条目") # Replaced by table

        if entries:
            table = Table(title=f"RSS 源解析结果 ({len(entries)} 条)", show_header=True, header_style="bold magenta")
            table.add_column("发布日期", style="dim", width=12)
            table.add_column("标题")
            table.add_column("Torrent 链接", style="blue")

            for entry in entries:
                table.add_row(
                    entry['pubdate'],
                    entry['title'],
                    f"[link={entry['torrent']}]...{entry['torrent'][-20:]}[/link]" if entry['torrent'] != 'N/A' else 'N/A'
                )
            console.print(table)
        else:
            console.log("[yellow]RSS 源中未找到有效条目。[/yellow]")

        return entries
    except Exception as e:
        console.log(f"[red]获取或解析 RSS 失败: {e}[/red]")
        return []


# 根据种子对应的发布时间获取或创建存放该种子的文件夹
async def get_folder_id(account_index, torrent_info):
    client = PIKPAK_CLIENTS[account_index]
    if not client:
        console.log(f"[red]账号 {account_index} 客户端无效，无法获取文件夹ID。[/red]")
        return None
    folder_path = PATH[account_index]
    pubdate = torrent_info['pubdate'] # Use pubdate from torrent_info
    if not pubdate or pubdate == 'N/A':
        console.log(f"[yellow]无法获取发布日期，将使用根目录: {torrent_info['title']}[/yellow]")
        return folder_path # Use root path if no date

    console.log(f"检查日期文件夹 [magenta]{pubdate}[/magenta] 是否存在...")
    try:
        # 获取文件夹列表
        folder_list = await client.file_list(parent_id=folder_path)
        for file in folder_list.get('files', []):
            if file.get('kind') == 'drive#folder' and file.get('name') == pubdate:
                console.log(f"找到文件夹 [magenta]{pubdate}[/magenta] (ID: {file['id']})")
                return file['id']
        # 未找到则创建新文件夹
        console.log(f"文件夹 [magenta]{pubdate}[/magenta] 不存在，正在创建...")
        folder_info = await client.create_folder(name=pubdate, parent_id=folder_path)
        new_folder_id = folder_info.get('file', {}).get('id')
        if new_folder_id:
            console.log(f"[green]成功创建文件夹[/green] [magenta]{pubdate}[/magenta] (ID: {new_folder_id})")
            return new_folder_id
        else:
            console.log(f"[red]创建文件夹 {pubdate} 失败: 返回信息不包含 ID[/red]")
            return None
    except Exception as e:
        console.log(f"[red]获取或创建文件夹 {pubdate} 失败: {e}[/red]")
        return None

# 通过解析 RSS 查找 torrent 对应的发布时间 (Deprecated, info passed directly)
# async def get_date(torrent):
#     mylist = await get_rss()
#     for entry in mylist:
#         if entry['torrent'] == torrent:
#             console.log(f"种子标题: {entry['title']}")
#             console.log(f"发布时间: {entry['pubdate']}")
#             return entry['pubdate']
#     return None


# 提交离线磁力任务至 PikPak
async def magnet_upload(account_index, torrent_info, folder_id):
    client = PIKPAK_CLIENTS[account_index]
    if not client:
        console.log(f"[red]账号 {account_index} 客户端无效，无法添加离线任务。[/red]")
        return None, None
    file_url = torrent_info['torrent']
    title = torrent_info['title']
    console.log(f"准备添加离线任务: [blue]{title}[/blue] 到文件夹 ID: {folder_id}")
    try:
        result = await client.offline_download(file_url=file_url, parent_id=folder_id)
        task_id = result.get('task', {}).get('id')
        task_name = result.get('task', {}).get('name')
        if task_id:
            console.log(f"[green]账号 {USER[account_index]} 添加离线任务成功:[/green] [blue]{task_name}[/blue] (ID: {task_id})")
            return task_id, task_name
        else:
            console.log(f"[red]账号 {USER[account_index]} 添加离线任务失败: 返回结果未包含任务信息. URL: {file_url}[/red]")
            return None, None
    except Exception as e:
        console.log(
            f"[red]账号 {USER[account_index]} 添加离线磁力任务失败: {e}. URL: {file_url}[/red]")
        return None, None


# 下载 torrent 文件并保存到本地
async def download_torrent(name, torrent_url, progress: Progress):
    console.log(f"准备下载种子文件: [blue]{name}[/blue] 从 [link={torrent_url}]{torrent_url}[/link]")
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Use stream=True for progress bar
            async with client.stream("GET", torrent_url, timeout=60.0) as response:
                response.raise_for_status() # Raise exception for bad status codes
                total_size = int(response.headers.get('content-length', 0))
                os.makedirs('torrent', exist_ok=True)
                file_path = os.path.join('torrent', name)

                # Use the passed progress object directly
                download_task = progress.add_task(f"[cyan]下载 {name}...", total=total_size)
                with open(file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                        progress.update(download_task, advance=len(chunk))
                progress.remove_task(download_task) # Remove task when done

        console.log(f"[green]种子文件下载完成:[/green] [blue]{file_path}[/blue]")
        return file_path
    except httpx.HTTPStatusError as e:
        console.log(f"[red]下载种子文件失败 (HTTP Status {e.response.status_code}): {name} from {torrent_url}[/red]")
        return None
    except Exception as e:
        console.log(f"[red]下载种子文件时发生错误: {e}. URL: {torrent_url}[/red]")
        return None


# 检查本地是否存在种子文件；若不存在则下载并提交离线任务
async def check_torrent(account_index, torrent_info, check_mode: str, progress: Progress):
    name = torrent_info['torrent'].split('/')[-1]
    torrent_url = torrent_info['torrent']
    title = torrent_info['title']
    local_path = os.path.join('torrent', name)

    if not os.path.exists(local_path):
        console.log(f"本地未找到种子文件: [blue]{name}[/blue]")
        if check_mode == "local":
            return True # Needs network check
        else:
            client = PIKPAK_CLIENTS[account_index]
            if not client:
                 console.log(f"[red]账号 {account_index} 客户端无效，无法检查云端任务。[/red]")
                 return False

            # --- Optimization: Check global task list first ---
            try:
                console.log(f"检查全局离线任务列表是否存在: [blue]{title}[/blue]")
                tasks = await client.offline_list()
                for task in tasks.get('tasks', []):
                    # Check if task name matches the torrent title
                    if task.get('name') == title:
                        console.log(f"[yellow]全局离线任务已存在，跳过添加: {title} (任务状态: {task.get('status_text', '未知')})[/yellow]")
                        return False # Already exists in global tasks
            except Exception as e:
                console.log(f"[yellow]检查全局离线任务列表失败: {e}，将继续后续检查。[/yellow]")
            # --- End Optimization ---

            # Download torrent using the passed progress object
            downloaded_path = await download_torrent(name, torrent_url, progress)
            if not downloaded_path:
                return False # Download failed, skip upload

            # Get folder ID
            folder_id = await get_folder_id(account_index, torrent_info)
            if not folder_id:
                console.log(f"[red]无法获取或创建目标文件夹，跳过离线任务: {title}[/red]")
                return False # Folder creation failed, skip upload

            # Fallback: Check if file already exists in the target folder (using name as a simple check)
            # This is kept as a secondary check in case the global task list check fails or misses something
            try:
                console.log(f"检查云端文件夹 [magenta]{folder_id}[/magenta] 是否已存在文件: [blue]{title}[/blue]")
                sub_folder_list = await client.file_list(parent_id=folder_id)
                for sub_file in sub_folder_list.get('files', []):
                     if (sub_file.get('name') == title or
                        (sub_file.get('params') and sub_file['params'].get('task_name') == title) or
                        (sub_file.get('params') and sub_file['params'].get('filename') == title)):
                         console.log(f"[yellow]云端文件夹中已存在同名文件，跳过添加: {title}[/yellow]")
                         # Optionally delete the downloaded torrent if it exists in the cloud folder
                         # if os.path.exists(downloaded_path):
                         #     os.remove(downloaded_path)
                         #     console.log(f"[dim]已删除本地重复种子: {downloaded_path}[/dim]")
                         return False # Already exists in folder
            except Exception as e:
                console.log(f"[yellow]检查云端文件夹失败: {e}，将尝试添加任务。[/yellow]")

            # Upload torrent
            await magnet_upload(account_index, torrent_info, folder_id)
            return True # Task submitted (or attempted)
    else:
        # console.log(f"本地已存在种子文件: [blue]{name}[/blue]") # Reduce verbosity
        return False # Already exists locally, no network check needed


async def main():
    console.rule("[bold blue]开始 RSS 检查[/bold blue]")
    # 刷新 token
    await auto_refresh_token()

    if not PIKPAK_CLIENTS[0]:
        console.log("[red]PikPak 客户端未初始化或登录失败，无法继续。[/red]")
        return

    # 获取 RSS 种子列表
    mylist = await get_rss()
    if not mylist:
        # console.log("[yellow]未能从 RSS 源获取任何条目。[/yellow]") # Message handled in get_rss
        console.rule("[bold blue]RSS 检查结束[/bold blue]")
        return

    # 先检查本地文件是否存在，减少重复请求次数
    console.log("开始本地检查...")
    needs_network_check_list = []
    # Use Progress for local check visualization
    with Progress(console=console) as progress_local:
        task_local_check = progress_local.add_task("[yellow]本地检查...", total=len(mylist))
        for entry in mylist:
            if entry['torrent'] == 'N/A':
                console.log(f"[yellow]跳过无效条目 (无 torrent 链接): {entry['title']}[/yellow]")
                progress_local.update(task_local_check, advance=1)
                continue
            # Pass the progress object to check_torrent for local check (though it won't be used there)
            needs_network = await check_torrent(0, entry, "local", progress_local)
            if needs_network:
                needs_network_check_list.append(entry)
            progress_local.update(task_local_check, advance=1)

    # 如果需要下载文件，则登录（若有token，实际上是复用之前的连接状态）
    if needs_network_check_list:
        console.log(f"发现 {len(needs_network_check_list)} 个新条目需要处理，开始网络检查和下载...")
        # await login(0) # Login is implicitly handled by token check/refresh

        # Create a single Progress instance for all downloads in this run
        with Progress(console=console) as progress_network:
            # Use Progress for network check/download visualization
            task_network_check = progress_network.add_task("[cyan]网络检查与下载...", total=len(needs_network_check_list))
            tasks = []
            for entry in needs_network_check_list:
                # Pass the single progress_network object to check_torrent
                tasks.append(check_torrent(0, entry, "network", progress_network))
                # No need to update task_network_check here, download_torrent handles its own task

            results = await asyncio.gather(*tasks)
            # Update the main task after all downloads are attempted/done
            progress_network.update(task_network_check, completed=len(needs_network_check_list))

        successful_uploads = sum(1 for r in results if r is True)
        failed_or_skipped = len(needs_network_check_list) - successful_uploads
        console.log(f"网络检查与下载完成: {successful_uploads} 个任务成功提交/跳过，{failed_or_skipped} 个失败/已存在。")
    else:
        console.log("本地检查完成，没有发现需要下载的新条目。")

    console.rule("[bold blue]RSS 检查结束[/bold blue]")


def setup_logging(
    log_file="rss-pikpak-cli.log", # Use a different log file
    log_level=logging.INFO,
    # max_bytes=10*1024*1024,  # Handled by Rich
    # backup_count=5
):
    """配置日志系统 (使用 RichHandler)"""
    logging.basicConfig(
        level=log_level,
        format="%(message)s", # Rich handles formatting
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)] # Use Rich handler
    )
    # Removed file handler section causing the error
    # logger = logging.getLogger("rich") # Get logger instance
    # console.log("[green]Rich 日志系统初始化成功[/green]")
    # return logger # Not needed to return logger explicitly

# --- Main Execution --- #

if __name__ == "__main__":
    # Initialize console early for any startup messages
    # console = Console()

    setup_logging()
    load_config()
    init_clients()
    # update_config() # Update config only if changed, perhaps via arguments later

    # 处理退出情况
    def signal_handler(sig, frame):
        console.print("\n[bold yellow]接收到退出信号...[/bold yellow]")
        console.log("正在保存状态并退出...")
        save_client()  # 保存客户端状态
        # update_config() # Avoid unnecessary config writes on exit
        console.log("状态保存完毕，程序退出。")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    console.rule("[bold green]PikPak RSS 下载器启动[/bold green]")
    console.print(f"用户: [cyan]{USER[0]}[/cyan]")
    console.print(f"RSS源: [link={RSS[0]}]{RSS[0]}[/link]")
    console.print(f"检查间隔 (RSS): {INTERVAL_TIME_RSS} 秒")
    console.print(f"检查间隔 (Token Refresh): {INTERVAL_TIME_REFRESH / 3600:.1f} 小时")
    console.print(f"PikPak 路径 ID: [yellow]{PATH[0]}[/yellow]")
    console.print("-" * 30) # Simple separator

    try:
        while True:
            asyncio.run(main())
            console.print(f"\n下次 RSS 检查将在 [cyan]{INTERVAL_TIME_RSS}[/cyan] 秒后进行...", style="dim")
            time.sleep(INTERVAL_TIME_RSS)
    except KeyboardInterrupt:
        console.print("\n[yellow]用户手动中断。[/yellow]")
        signal_handler(signal.SIGINT, None) # Call handler to save state
    except Exception as e:
        console.print("\n[bold red]发生未处理的异常:[/bold red]")
        console.print_exception(show_locals=False) # Use rich's exception printing
        save_client() # Attempt to save state on unexpected error
        sys.exit(1)