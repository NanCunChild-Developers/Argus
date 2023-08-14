import win32cred


def enumerate_credentials():
    try:
        # 以空用户名和密码访问凭据，表示使用当前用户的凭据
        creds = win32cred.CredEnumerate(None, 0)
        for cred in creds:
            target = cred['TargetName']
            username = cred['UserName']
            password = cred['CredentialBlob'].decode()
            print(f"目标名称: {target}")
            print(f"用户名: {username}")
            print(f"密码: {password}")
            print("=" * 30)
    except Exception as e:
        print("枚举凭据失败:", str(e))


if __name__ == "__main__":
    enumerate_credentials()
