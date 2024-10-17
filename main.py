# 导入必要的系统模块
import sys
import os
import subprocess

# 导入日志和异常追踪模块
import logging
import traceback

# 导入PyQt5相关模块
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# 导入自定义的GUI模块
from gui.main_window import VideoProcessorGUI

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

print("Python 路径:")
print(sys.executable)

print("\n已安装的包:")
result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
print(result.stdout)

# 强制使用系统 Python
if sys.prefix != sys.base_prefix:
    os.execl(sys.executable, sys.executable, *sys.argv)

def setup_logging():
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def exception_hook(exctype, value, tb):
    logging.error('Uncaught exception:', exc_info=(exctype, value, tb))
    traceback.print_exception(exctype, value, tb)
    QtWidgets.QApplication.quit()

def main():
    setup_logging()
    sys.excepthook = exception_hook
    try:
        app = QApplication(sys.argv)
        
        # 设置应用图标
        icon_path = os.path.join(os.path.dirname(__file__), 'app_icon.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        ex = VideoProcessorGUI()
        ex.show()
        
        logging.info("RandFrameDel 启动成功")
        
        ret = app.exec_()
        sys.exit(ret)
    except Exception as e:
        logging.error(f"RandFrameDel 运行出错: {str(e)}", exc_info=True)
        # 可以在这里添加一个消息框来显示错误信息
        error_box = QtWidgets.QMessageBox()
        error_box.setIcon(QtWidgets.QMessageBox.Critical)
        error_box.setText("程序遇到了一个错误")
        error_box.setInformativeText(str(e))
        error_box.setWindowTitle("错误")
        error_box.exec_()

if __name__ == '__main__':
    main()
