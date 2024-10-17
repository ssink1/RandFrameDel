import os
import sys
import shutil
import PyInstaller.__main__

def build_app():
    # 获取当前脚本的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置主脚本路径
    main_script = os.path.join(current_dir, 'main.py')
    
    # 设置图标路径
    icon_path = os.path.join(current_dir, 'app_icon.ico')
    
    # 设置输出目录
    output_dir = os.path.join(current_dir, 'dist')
    
    # 如果输出目录已存在，则删除它
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    # PyInstaller参数
    pyinstaller_args = [
        main_script,
        '--name=RandFrameDel',
        '--onefile',
        f'--icon={icon_path}',
        '--windowed',
        '--add-data=app_icon.ico:.',
        '--hidden-import=PyQt5',
        '--hidden-import=cv2',
        '--hidden-import=numpy',
        '--hidden-import=moviepy',
        '--add-binary=ffmpeg.exe;.',
        '--add-binary=ffprobe.exe;.'
    ]
    
    # 运行PyInstaller
    PyInstaller.__main__.run(pyinstaller_args)
    
    print("构建完成。可执行文件位于 'dist' 目录中。")

if __name__ == '__main__':
    build_app()
