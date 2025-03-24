import os
import re


def parse_tree_file(tree_file_path, output_dir):
    with open(tree_file_path, 'r', encoding='gbk') as f:
        lines = f.readlines()

    current_path = output_dir
    path_stack = [output_dir]  # 路径栈，初始为输出根目录
    last_depth = 0  # 上一行的缩进深度

    for line in lines:
        line = line.strip('\n').rstrip()  # 去除换行符和右侧空格
        if not line:
            continue

        if line.find(':') >= 0:
            continue

        # 计算当前行的缩进深度（通过符号数量）
        depth = (len(re.findall(r'[│├└]', line)) + line.count('    ')) // 1  # 根据符号数量估算层级
        name = re.sub(r'[│├└─ ]+', '', line)  # 提取纯净的目录/文件名

        # 动态调整路径栈
        if depth > last_depth:
            path_stack.append(os.path.join(current_path, name))  # 进入子目录
        elif depth < last_depth:
            for _ in range(last_depth - depth + 1):
                path_stack.pop() # 返回上级目录
            path_stack.append(os.path.join(path_stack[-1], name))

        # 构建当前完整路径
        current_path = os.path.join(path_stack[-1])
        if not os.path.exists(current_path):
            os.makedirs(current_path, exist_ok=True)  # 创建目录

        last_depth = depth


if __name__ == "__main__":
    parse_tree_file("tree.txt", "e:/test")