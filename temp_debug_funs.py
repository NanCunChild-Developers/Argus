import json
import socket

# 设置服务器的IP地址和端口号
server_ip = "127.0.0.1"
server_command_port = 1818
server_inform_port = 1819

client_id = ""
process = None

class NetworkConnection:
    @staticmethod
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