import os

def get_file_size(file_path):
    return os.path.getsize(file_path)

def get_output_path(input_path):
    base, ext = os.path.splitext(input_path)
    return f"{base}_processed{ext}"

def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def is_valid_video_file(file_path):
    valid_extensions = ('.mp4', '.avi', '.mov')
    return os.path.isfile(file_path) and file_path.lower().endswith(valid_extensions)
