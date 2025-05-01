#!/bin/bash

# 检查channels.json文件是否存在，如果不存在则创建
if [ ! -f channels.json ]; then
    echo "创建空的channels.json文件..."
    echo "[]" > channels.json
fi

# 检查uploads目录是否存在，如果不存在则创建
if [ ! -d uploads ]; then
    echo "创建uploads目录..."
    mkdir -p uploads
fi

# 启动应用程序
echo "启动IPTV Web客户端..."
python app.py