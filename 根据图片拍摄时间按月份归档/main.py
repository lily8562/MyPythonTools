import os
import shutil
import zipfile
import exifread
from datetime import datetime
from PIL import Image
import tempfile

# 安装依赖：pip install pillow-heif exifread
try:
    import pillow_heif  # HEIC格式支持
except ImportError:
    pass

def get_media_date(file_path):
    """获取媒体文件的创建时间（优先EXIF，若无则用修改时间）"""
    try:
        # 处理图片/视频的EXIF或元数据
        if file_path.lower().endswith(('.heic', '.jpg', '.jpeg', '.png')):
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f)
                date_str = str(tags.get('EXIF DateTimeOriginal', ''))
                if date_str:
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass

    # 回退到文件修改时间
    file_stat = os.stat(file_path)
    return datetime.fromtimestamp(file_stat.st_mtime)

def process_livp_file(livp_path, dest_root):
    """解压LIVP文件并处理内部HEIC图片"""
    temp_dir = tempfile.mkdtemp()
    try:
        # 解压LIVP（本质是ZIP格式）
        with zipfile.ZipFile(livp_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 处理解压后的HEIC文件
        for root, _, files in os.walk(temp_dir):
            for filename in files:
                if filename.lower().endswith('.heic'):
                    src_path = os.path.join(root, filename)
                    date_taken = get_media_date(src_path)
                    month_folder = date_taken.strftime("%Y-%m")
                    dest_dir = os.path.join(dest_root, month_folder)
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # 移动文件并保留元数据
                    shutil.move(src_path, os.path.join(dest_dir, filename))
    finally:
        shutil.rmtree(temp_dir)  # 清理临时文件夹

def classify_media_by_month(src_dir, dst_dir):
    """主函数：按月份分类媒体文件（支持图片/视频/LIVP）"""
    supported_ext = ('.jpg', '.jpeg', '.png', '.heic', '.mp4', '.mov', '.livp')
    
    for root, _, files in os.walk(src_dir):
        for filename in files:
            src_path = os.path.join(root, filename)
            if filename.lower().endswith(supported_ext):
                try:
                    if filename.lower().endswith('.livp'):
                        # 处理LIVP文件
                        process_livp_file(src_path, dst_dir)
                    else:
                        # 处理普通图片/视频
                        date_taken = get_media_date(src_path)
                        month_folder = date_taken.strftime("%Y-%m")
                        dest_dir = os.path.join(dst_dir, month_folder)
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.move(src_path, os.path.join(dest_dir, filename))
                    print(f"Processed: {filename}")
                except Exception as e:
                    print(f"Error processing {filename}: {str(e)}")

# 使用示例
if __name__ == "__main__":
    classify_media_by_month(
        src_dir="path/to/source_folder",
        dst_dir="path/to/destination_folder"
    )