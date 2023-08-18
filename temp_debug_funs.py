import os
import subprocess
import threading
import time


class CmdExecutor:
    def __init__(self):
        self.proc = subprocess.Popen(
            "cmd",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def execute(self, command):
        self.proc.stdin.write(command + '\n')
        self.proc.stdin.flush()
        result = self.proc.communicate()[0]
        print(result)
        return result, None  # 只读取一行作为示例


if __name__ == "__main__":
    executor = CmdExecutor()
    commands = input("Enter a command: ")
    stdout, _ = executor.execute(commands)
    print(stdout)
