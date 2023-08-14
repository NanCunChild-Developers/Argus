import time
import cv2
from PIL import ImageGrab
import numpy as np


def screenshot_and_save(file_path):
    try:
        while True:
            # 截取屏幕并保存到指定路径
            screen = ImageGrab.grab()
            screen.save(file_path, "PNG")

            # 等待10秒再次截屏
            time.sleep(10)
    except KeyboardInterrupt:
        print("截屏功能已停止。")


def capture_and_save_image():
    # 创建摄像机对象，参数为摄像机编号，一般为0代表默认摄像头
    cap = cv2.VideoCapture(0)

    # 检查摄像机是否成功打开
    if not cap.isOpened():
        print("无法打开摄像机")
        return

    # 从摄像机中读取一帧图像
    ret, frame = cap.read()

    # 检查是否成功读取图像
    if not ret:
        print("无法读取摄像机图像")
        cap.release()
        return

    # 保存图像为shoot.png
    cv2.imwrite('shoot.png', frame)

    # 释放摄像机资源
    cap.release()

    print("图片已保存为shoot.png")


def record_video(output_path, duration=10):
    # 打开摄像头
    cap = cv2.VideoCapture(0)

    # 设置视频编码器和帧率
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    fps = 30
    video_writer = cv2.VideoWriter(output_path, fourcc, fps, (640, 480))

    # 录制视频
    start_time = cv2.getTickCount()
    while (cv2.getTickCount() - start_time) / cv2.getTickFrequency() < duration:
        ret, frame = cap.read()
        if not ret:
            break

        # 将帧写入视频文件
        video_writer.write(frame)

        # 显示实时画面（可选）
        cv2.imshow('Recording', frame)
        if cv2.waitKey(1) & 0xFF == 27:  # 按下Esc键退出录制
            break

    # 释放摄像头和视频写入器资源
    cap.release()
    video_writer.release()
    cv2.destroyAllWindows()


def capture_frame(screen_size=(640, 480), interval=5):
    # 前后帧比较法
    # 初始化摄像头
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_size[1])

    # 初始化前一帧
    prev_frame = None

    while True:
        # 获取当前帧
        ret, frame = cap.read()

        if ret:
            # 将当前帧转换为灰度图像
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 如果前一帧为空，则初始化前一帧
            if prev_frame is None:
                prev_frame = gray_frame
                continue

            # 计算当前帧与前一帧的差异
            diff_frame = cv2.absdiff(gray_frame, prev_frame)

            # 根据差异阈值进行二值化
            _, thresh = cv2.threshold(diff_frame, 30, 255, cv2.THRESH_BINARY)

            # 计算差异图像中白色像素的个数
            white_pixel_count = np.sum(thresh == 255)

            # 判断是否有变化，这里可以根据具体场景调整阈值
            if white_pixel_count > 100:
                # 保存当前帧为图片
                filename = f"frame_{time.strftime('%Y%m%d%H%M%S')}.png"
                cv2.imwrite(filename, frame)
                print(f"保存截图 {filename}")

            # 更新前一帧
            prev_frame = gray_frame

        # 等待指定的时间间隔
        time.sleep(interval)

    # 释放摄像头
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    file_path = "screenshot.png"
    # screenshot_and_save(file_path)
    # capture_and_save_image()
    record_video('output.avi', duration=10)
    # 调用截屏函数
    capture_frame()