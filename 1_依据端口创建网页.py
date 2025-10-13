import shutil
from subprocess import Popen, PIPE, STDOUT
import os
import subprocess
import ctypes,sys
import time
# 创建复制谷歌浏览器
# 文件1参数设置
action = 1 #  0 创建端口浏览器，1开启端口浏览器，注意如果重新创建并成功，之前安装的东西都会没了
_chome_path = r"C:\Program Files\Google\Chrome\Application" # 谷歌浏览器所在路径 chome.exe所在的路径
_to_path = "E:\\myChome\\" # 复制到所在盘符地址（根据当前工作盘 E: 调整）
chome_port = 9222 # 浏览器起始占用端口,下面一个参数如果为 2，就会创建9222，9223批量创建
chome_sum = 1 # 创建端口数量

chome_port_list = []
for i in range(chome_sum):
    chome_port_list.append(chome_port+i)

def ensure_admin():
    """
    如果当前脚本没有管理员权限，则自动以管理员身份重新运行。
    """
    try:
        # 检查是否有管理员权限
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    if not is_admin:
        # 重新以管理员身份启动自己
        print("🔐 检测到当前无管理员权限，正在以管理员身份重新运行...")
        try:
            # ShellExecuteW 参数说明：
            # 1. None：句柄
            # 2. "runas"：请求管理员权限
            # 3. sys.executable：python解释器路径
            # 4. 参数字符串（当前脚本路径）
            # 5. None：工作目录
            # 6. 1：显示窗口
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
        except Exception as e:
            print(f"❌ 申请管理员权限失败: {e}")


# 🚀 调用一次即可


def create_chome_file():

    chrome_exe = os.path.join(_chome_path, "chrome.exe")
    if not os.path.isfile(chrome_exe):
        print("chrome.exe 路径不存在，请检查 _chome_path 设置")
        exit()

    for i in chome_port_list:
        # 为每个端口准备独立的用户数据目录
        to_path = os.path.join(_to_path, str(i))
        try:
            os.makedirs(to_path, exist_ok=True)
            print("已准备用户数据目录 {}".format(to_path))
        except Exception as e:
            print("创建用户数据目录失败:", to_path, e)



def open_chrome():

    chrome_exe = os.path.join(_chome_path, "chrome.exe")
    if not os.path.isfile(chrome_exe):
        print("chrome.exe 路径不存在，请检查 _chome_path 设置")
        exit()

    for port in chome_port_list:
        user_data_dir = os.path.join(_to_path, str(port))
        os.makedirs(user_data_dir, exist_ok=True)

        # 启动时打开的网页（可按需修改）
        url1 = "https://www.binance.com/zh-CN/"

        # 构建 Chrome 启动命令
        command = (
            f'"{chrome_exe}" '
            f'--remote-debugging-port={port} '
            f'--user-data-dir="{user_data_dir}" '
            f'--no-first-run '
            f'--disable-background-networking '
            f'--disable-component-update '
            f'--disable-default-apps '
            f'--disable-sync '
            f'--disable-prompt-on-repost '
            f'"{url1}"'
        )
        try:
            subprocess.Popen(command, shell=True)
            print(f"Chrome launched on port {port} with user data dir {user_data_dir}")
            time.sleep(5)
        except Exception as e:
            print(f"Failed to launch Chrome on port {port}: {e}")


if __name__ == '__main__':

    # 启用管理员权限
    ensure_admin()
    # 你的代码逻辑在这里
    if action == 0:
        # 批量创建谷歌浏览器
        create_chome_file()
    else:
        # 通过端口开启浏览器
        open_chrome()
