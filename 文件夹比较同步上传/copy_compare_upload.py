import os
import time
import subprocess
import shutil  # 引入 shutil 模块，用于文件拷贝和删除目录树
import pywintypes
import win32file
import win32con
import logging # 引入 logging 模块，用于记录日志
import stat

folder_A = r"F:\ShareCache\软件文档库\软件产品库\软件产品发布"  # 基准文件夹 (左侧)
folder_B = r"F:\BaiduSyncdisk\ShareCache\软件文档库\软件产品库\软件产品发布" # 待比较文件夹 (右侧)
net_pan_path = r"/软件同步目录/" # 百度网盘根路径

def copy_file_preserve_metadata(src, dst):
    """复制文件并保留所有元数据，包括创建时间（Windows）"""
    try:
        # 使用 copy2 复制文件和大部分元数据（包括修改时间和访问时间）
        shutil.copy2(src, dst)
        print(f"文件已复制: {src} -> {dst}")
        
        # 检查目标文件是否存在, 且是否可写
        if os.path.exists(dst) and not os.access(dst, os.W_OK):
            os.chmod(dst, stat.S_IWRITE) 
        
        # 获取源文件的创建时间
        src_stat = os.stat(src)
        creation_time = src_stat.st_ctime  # 获取源文件创建时间戳
        
        # 将时间戳转换为Windows API所需的格式
        pywin_time = pywintypes.Time(creation_time)
        
        # 打开目标文件句柄以设置时间
        handle = win32file.CreateFile(
            dst,
            win32con.GENERIC_WRITE,
            win32con.FILE_SHARE_READ,
            None,
            win32con.OPEN_EXISTING,
            0,
            None
        )
        
        # 设置文件创建时间（其他时间参数设为None则保持不变）
        win32file.SetFileTime(handle, pywin_time, None, None)
        
        # 关闭文件句柄
        handle.Close()
        return True
        
    except Exception as e:
        print(f"操作失败: {e}")
        return False


def compare_folders(left_dir, right_dir):
    """
    比较两个文件夹的差异。
    以 left_dir 为基准，分析 right_dir 的变化。
    比较标准：文件大小、文件创建时间。

    :param left_dir: 基准文件夹路径 (A)
    :param right_dir: 待比较文件夹路径 (B)
    :return: (added, deleted, modified)
             added: B 中有, A 中没有的文件 (相对路径列表)
             deleted: A 中有, B 中没有的文件 (相对路径列表)
             modified: 两侧都有，但属性不同的文件 (元组列表 [(相对路径, 差异详情), ...])
    """
    
    # 1. 遍历基准文件夹 (A)
    left_files = {}
    for root, _, files in os.walk(left_dir):
        for filename in files:
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, left_dir)
            try:
                stats = os.stat(full_path)
                creation_time = stats.st_ctime
                file_size = stats.st_size
                left_files[relative_path] = (creation_time, file_size)
            except FileNotFoundError:
                continue

    # 2. 准备记录差异的列表
    added_files = []
    modified_files = [] # 将存储为 (relative_path, details) 的元组
    
    left_files_copy = left_files.copy()

    # 3. 遍历待比较文件夹 (B)
    for root, _, files in os.walk(right_dir):
        for filename in files:
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, right_dir)
            try:
                stats = os.stat(full_path)
                creation_time = stats.st_ctime
                file_size = stats.st_size
            except FileNotFoundError:
                continue

            if relative_path not in left_files:
                # 情况1: 新增文件 (在 B 中存在，在 A 中不存在)
                added_files.append(relative_path)
            else:
                # 文件存在于两侧，比较属性
                left_creation_time, left_file_size = left_files[relative_path]
                
                reasons = []
                if abs(creation_time - left_creation_time) > 2.5:
                    reasons.append("创建时间不同")
                if file_size != left_file_size:
                    reasons.append("文件大小不同")

                if reasons:
                    # 情况2: 修改过的文件
                    details = f"({', '.join(reasons)})"
                    # 存储元组 (路径, 详情)
                    modified_files.append((relative_path, details))

                del left_files_copy[relative_path]

    # 4. 查找被删除的文件 (A 中有, B 中没有)
    deleted_files = list(left_files_copy.keys())

    return added_files, deleted_files, modified_files

def setup_logging():
    """配置日志记录器"""
    # 配置日志记录
    logger = logging.getLogger('FolderSync')
    logger.setLevel(logging.INFO)
    
    # 防止重复添加 handler
    if not logger.handlers:
        # 1. 输出到文件
        file_handler = logging.FileHandler('sync_log.txt', mode='a', encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 2. 输出到控制台
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
    return logger


def upload_baidu_pan(src_file, dest_path):
    posix_rel_path = dest_path.replace("\\", "/")
    cmd_upload = ['BaiduPCS-Go.exe','upload', src_file, os.path.dirname(net_pan_path + posix_rel_path)] 
    # 脚本会在这里“卡住”，直到 command 完成
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd_upload,
            capture_output=True, # 捕获输出
            text=True,           # 将输出解码为文本
            check=True,          # 如果命令失败（返回非零值），则抛出异常
            encoding='utf-8'     # 明确使用 utf-8 编码，防止中文乱码
        )
        print(result.stdout)
        end_time = time.time()
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] 网盘上传完成！(耗时: {end_time - start_time:.2f} 秒),cmd:{cmd_upload}")
        return True
    except subprocess.CalledProcessError as e:
        # 如果 BaiduPCS-Go 执行失败
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] Python 脚本:BaiduPCS-Go 执行失败！")
        logger.info(f"错误码: {e.returncode}, 标准错误: \n{e.stderr}")
        return False
    except Exception as e:
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] 发生意外错误: {e}")
        return False


def delete_baidu_pan(dest):
    try:
        posix_rel_path = dest.replace("\\", "/")
        cmd_del = ['BaiduPCS-Go.exe','rm', net_pan_path + posix_rel_path]
        start_time = time.time()
        
        result = subprocess.run(
            cmd_del,
            capture_output=True, # 捕获输出
            text=True,           # 将输出解码为文本
            check=True,          # 如果命令失败（返回非零值），则抛出异常
            encoding='utf-8'     # 明确使用 utf-8 编码，防止中文乱码
        )
        print(result.stdout)
        end_time = time.time()
        
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] 网盘上传完成！(耗时: {end_time - start_time:.2f} 秒),cmd:{cmd_del}")   
        return True      
    except subprocess.CalledProcessError as e:
        # 如果 BaiduPCS-Go 执行失败
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] Python 脚本:BaiduPCS-Go 执行失败！")
        logger.info(f"错误码: {e.returncode}, 标准错误: \n{e.stderr}")
        return False      
    except Exception as e:
        logger.info(f"\n[{time.strftime('%H:%M:%S')}] 发生意外错误: {e}")
        return False      
        

if __name__ == "__main__":

    # 1. 设置日志
    logger = setup_logging()
    logger.info("-" * 80)
    print(f"--- 开始单向同步 ---")
    print(f"基准文件夹 (A): {folder_A}")
    print(f"目标文件夹 (B): {folder_B}")
    print("同步方向: A -> B (B将被修改以匹配A)")
    print("-" * 80)

    # 2. 检查路径
    if not os.path.isdir(folder_A):
        print(f"错误: 基准文件夹 '{folder_A}' 不存在或不是一个目录。")
        exit()
    if not os.path.isdir(folder_B):
        print(f"警告: 目标文件夹 '{folder_B}' 不存在。将自动创建。")
        try:
            os.makedirs(folder_B)
            print(f"已创建目标文件夹: {folder_B}")
        except Exception as e:
            print(f"无法创建目标文件夹: {e}")
            exit()

    # 3. 执行比较
    try:
        added, deleted, modified = compare_folders(folder_A, folder_B)
    except Exception as e:
        logger.error(f"比较过程中发生错误: {e}")
        exit()
        
    logger.info(f"比较完成。发现: B中多余 {len(added)} 个, B中缺少 {len(deleted)} 个, 需更新 {len(modified)} 个")
    logger.info("-" * 40)

    # 4. 执行同步操作
    
    # 4.1  执行修改动作，即用A替换B
    for rel_path, details in modified:
        
        source_path = os.path.join(folder_A, rel_path)
        dest_path = os.path.join(folder_B, rel_path)
        
        # 确保目标子目录存在
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        if delete_baidu_pan(rel_path) is False:
            continue
        
        # 特殊覆盖，替换文件同时，修改文件创建时间，提高后续文件比对速度
        if copy_file_preserve_metadata(source_path, dest_path):
            print(f"[覆盖] {dest_path} {details}")
        else:          
            logger.error(f"覆盖文件失败: {source_path} -> {dest_path}")
            continue
        
        if upload_baidu_pan(dest_path, rel_path) is False:
            continue

    
    # 4.2 执行新增动作，  A 中存在、B 中不存在的文件 ，从A拷贝到B
    for rel_path in deleted:
        
        source_path = os.path.join(folder_A, rel_path)
        dest_path = os.path.join(folder_B, rel_path)
        
        # 确保目标子目录存在
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
        if copy_file_preserve_metadata(source_path, dest_path):
            logger.info(f"[新增] {dest_path}, 相对目录 {rel_path}")
        else:          
            logger.error(f"拷贝文件失败: {source_path} -> {dest_path}")
            continue
        
        upload_baidu_pan(dest_path, rel_path)        


    # 4.3 执行删除动作， B 中存在、A中不存在的文件 ，删除B中的文件
    for rel_path in sorted(added, key=len, reverse=True):
        try:
            file_to_delete = os.path.join(folder_B, rel_path)
            os.remove(file_to_delete)
            logger.info(f"[删除] {file_to_delete}, 相对目录 {rel_path}")
        except FileNotFoundError:
            logger.warning(f"试图删除文件失败，文件已不存在: {file_to_delete}")
            continue
        except Exception as e:
            logger.error(f"删除文件失败: {file_to_delete} | 错误: {e}")
            continue
        
        delete_baidu_pan(file_to_delete)     
        
    
    logger.info("-" * 25)
    
    # 5. 最终报告 (打印到控制台)
    print("\n--- 同步结果摘要 ---")
    if not added and not deleted and not modified:
        print("两个文件夹内容已保持一致。")
    else:
        print(f"操作完成:")
        print(f"  新增/覆盖到 B (来自 A): {len(deleted) + len(modified)} 个")
        print(f"  从 B 中删除 (A 中没有): {len(added)} 个")
        
    print(f"\n详细日志已保存到: {os.path.abspath('sync_log.txt')}")
    print("--- 同步完成 ---")

