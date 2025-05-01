#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于Flask的IPTV Web客户端
"""

import os
import json
import requests
import concurrent.futures
import time
import urllib.parse
import base64
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, Response, stream_with_context
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 用于session加密
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 存储频道列表的文件
CHANNELS_FILE = 'channels.json'

def load_channels():
    """从JSON文件加载频道列表"""
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_channels(channels):
    """保存频道列表到JSON文件"""
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

def test_channel_url(url, timeout=5):
    """测试频道URL是否可访问"""
    try:
        # 对于m3u8文件，只请求头部信息
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 使用HEAD请求检查URL是否可访问
        response = requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
        
        # 如果HEAD请求失败，尝试GET请求
        if response.status_code >= 400:
            response = requests.get(url, timeout=timeout, headers=headers, stream=True)
            # 只读取一小部分内容
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    break
        
        return {
            'url': url,
            'status': 'online' if response.status_code < 400 else 'offline',
            'status_code': response.status_code
        }
    except requests.RequestException as e:
        return {
            'url': url,
            'status': 'error',
            'error': str(e)
        }

def test_channels_batch(channels, max_workers=10):
    """批量测试多个频道URL"""
    urls = [channel['url'] for channel in channels]
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(test_channel_url, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results[url] = result
            except Exception as e:
                results[url] = {
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                }
    
    # 更新频道状态
    for channel in channels:
        if channel['url'] in results:
            channel['status'] = results[channel['url']]['status']
            if 'status_code' in results[channel['url']]:
                channel['status_code'] = results[channel['url']]['status_code']
            if 'error' in results[channel['url']]:
                channel['error'] = results[channel['url']]['error']
    
    return channels

def parse_m3u(content):
    """解析M3U/M3U8文件内容"""
    channels = []
    lines = content.splitlines()
    
    channel_name = None
    channel_logo = None
    channel_group = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#EXTM3U'):
            continue
        elif line.startswith('#EXTINF'):
            # 解析频道信息
            info_part = line.split(',', 1)
            if len(info_part) > 1:
                channel_name = info_part[1].strip()
                
                # 尝试解析logo和group
                meta_part = info_part[0]
                if 'tvg-logo=' in meta_part:
                    logo_start = meta_part.find('tvg-logo="') + 10
                    logo_end = meta_part.find('"', logo_start)
                    if logo_start > 9 and logo_end > logo_start:
                        channel_logo = meta_part[logo_start:logo_end]
                
                if 'group-title=' in meta_part:
                    group_start = meta_part.find('group-title="') + 13
                    group_end = meta_part.find('"', group_start)
                    if group_start > 12 and group_end > group_start:
                        channel_group = meta_part[group_start:group_end]
            else:
                channel_name = f"Channel {len(channels) + 1}"
        elif not line.startswith('#') and channel_name:
            # 这是一个URL
            channel = {
                "name": channel_name,
                "url": line,
                "logo": channel_logo or "",
                "group": channel_group or "未分类",
                "status": "unknown"  # 初始状态为未知
            }
            channels.append(channel)
            channel_name = None
            channel_logo = None
            channel_group = None
    
    return channels

@app.route('/')
def index():
    """首页 - 显示频道列表"""
    channels = load_channels()
    
    # 为每个频道添加全局索引
    for i, channel in enumerate(channels):
        channel['global_id'] = i
    
    # 获取所有频道分组
    groups = sorted(list(set(channel['group'] for channel in channels)))
    
    # 按分组组织频道
    channels_by_group = {}
    for group in groups:
        channels_by_group[group] = [c for c in channels if c['group'] == group]
    
    return render_template('index.html', channels_by_group=channels_by_group, groups=groups, all_channels=channels)

@app.route('/test_channels', methods=['GET', 'POST'])
def test_channels_route():
    """测试频道是否可访问"""
    if request.method == 'POST':
        channels = load_channels()
        
        if not channels:
            flash('没有频道可供测试', 'warning')
            return redirect(url_for('index'))
        
        # 获取选择的分组
        selected_group = request.form.get('group', 'all')
        
        # 根据选择的分组筛选频道
        if selected_group != 'all':
            test_channels = [c for c in channels if c['group'] == selected_group]
        else:
            test_channels = channels
        
        if not test_channels:
            flash('所选分组中没有频道可供测试', 'warning')
            return redirect(url_for('test_channels_route'))
        
        flash(f'正在测试 {len(test_channels)} 个频道，这可能需要一些时间...', 'info')
        
        # 测试频道
        start_time = time.time()
        test_channels = test_channels_batch(test_channels)
        end_time = time.time()
        
        # 更新原始频道列表中的状态
        for test_channel in test_channels:
            for channel in channels:
                if channel['url'] == test_channel['url']:
                    channel['status'] = test_channel['status']
                    if 'status_code' in test_channel:
                        channel['status_code'] = test_channel['status_code']
                    if 'error' in test_channel:
                        channel['error'] = test_channel['error']
        
        # 保存更新后的频道列表
        save_channels(channels)
        
        # 统计在线和离线频道数量
        online_count = sum(1 for c in test_channels if c['status'] == 'online')
        offline_count = sum(1 for c in test_channels if c['status'] == 'offline')
        error_count = sum(1 for c in test_channels if c['status'] == 'error')
        
        # 计算测试耗时
        test_time = end_time - start_time
        
        flash(f'测试完成，耗时 {test_time:.2f} 秒。在线: {online_count}, 离线: {offline_count}, 错误: {error_count}', 'success')
        
        return redirect(url_for('index'))
    
    # 获取所有频道分组
    channels = load_channels()
    groups = sorted(list(set(channel['group'] for channel in channels)))
    
    return render_template('test_channels.html', groups=groups)

@app.route('/play/<int:channel_id>')
def play(channel_id):
    """播放特定频道"""
    channels = load_channels()
    
    if 0 <= channel_id < len(channels):
        channel = channels[channel_id]
        return render_template('player.html', channel=channel, channel_id=channel_id, total_channels=len(channels))
    else:
        flash('频道不存在', 'error')
        return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_playlist():
    """上传播放列表"""
    if request.method == 'POST':
        # 检查是否有文件
        if 'playlist' not in request.files:
            flash('没有选择文件', 'error')
            return redirect(request.url)
        
        file = request.files['playlist']
        
        # 如果用户没有选择文件
        if file.filename == '':
            flash('没有选择文件', 'error')
            return redirect(request.url)
        
        if file:
            try:
                # 读取文件内容
                content = file.read().decode('utf-8')
                
                # 解析M3U文件
                channels = parse_m3u(content)
                
                if channels:
                    # 保存频道列表
                    save_channels(channels)
                    flash(f'成功加载 {len(channels)} 个频道', 'success')
                else:
                    flash('未找到任何频道', 'warning')
                
                return redirect(url_for('index'))
            
            except Exception as e:
                flash(f'处理文件时出错: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/add', methods=['GET', 'POST'])
def add_channel():
    """手动添加频道"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        url = request.form.get('url', '').strip()
        logo = request.form.get('logo', '').strip()
        group = request.form.get('group', '未分类').strip()
        
        if not name or not url:
            flash('频道名称和URL不能为空', 'error')
            return redirect(request.url)
        
        channels = load_channels()
        
        # 添加新频道
        channels.append({
            "name": name,
            "url": url,
            "logo": logo,
            "group": group
        })
        
        # 保存频道列表
        save_channels(channels)
        
        flash('频道添加成功', 'success')
        return redirect(url_for('index'))
    
    # 获取现有分组列表供选择
    channels = load_channels()
    groups = sorted(list(set(channel['group'] for channel in channels)))
    
    return render_template('add_channel.html', groups=groups)

@app.route('/edit/<int:channel_id>', methods=['GET', 'POST'])
def edit_channel(channel_id):
    """编辑频道"""
    channels = load_channels()
    
    if not (0 <= channel_id < len(channels)):
        flash('频道不存在', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        url = request.form.get('url', '').strip()
        logo = request.form.get('logo', '').strip()
        group = request.form.get('group', '未分类').strip()
        
        if not name or not url:
            flash('频道名称和URL不能为空', 'error')
            return redirect(request.url)
        
        # 更新频道信息
        channels[channel_id] = {
            "name": name,
            "url": url,
            "logo": logo,
            "group": group
        }
        
        # 保存频道列表
        save_channels(channels)
        
        flash('频道更新成功', 'success')
        return redirect(url_for('index'))
    
    # 获取现有分组列表供选择
    groups = sorted(list(set(channel['group'] for channel in channels)))
    
    return render_template('edit_channel.html', channel=channels[channel_id], channel_id=channel_id, groups=groups)

@app.route('/delete/<int:channel_id>', methods=['POST'])
def delete_channel(channel_id):
    """删除单个频道"""
    channels = load_channels()
    
    if 0 <= channel_id < len(channels):
        del channels[channel_id]
        save_channels(channels)
        flash('频道已删除', 'success')
    else:
        flash('频道不存在', 'error')
    
    return redirect(url_for('index'))

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    """批量删除频道"""
    delete_type = request.form.get('delete_type', '')
    delete_value = request.form.get('delete_value', '')
    
    channels = load_channels()
    
    if delete_type == 'all':
        # 删除所有频道
        channels = []
        save_channels(channels)
        flash('所有频道已删除', 'success')
    
    elif delete_type == 'group':
        # 删除指定分组的频道
        if delete_value:
            # 保留不属于指定分组的频道
            channels = [c for c in channels if c['group'] != delete_value]
            save_channels(channels)
            flash(f'"{delete_value}"分组中的所有频道已删除', 'success')
        else:
            flash('分组名称无效', 'error')
    
    elif delete_type == 'status':
        # 删除指定状态的频道
        if delete_value in ['online', 'offline', 'error', 'unknown']:
            # 保留不是指定状态的频道
            original_count = len(channels)
            channels = [c for c in channels if c.get('status', 'unknown') != delete_value]
            deleted_count = original_count - len(channels)
            save_channels(channels)
            
            status_map = {
                'online': '在线',
                'offline': '离线',
                'error': '错误',
                'unknown': '未测试'
            }
            
            flash(f'已删除 {deleted_count} 个{status_map.get(delete_value, delete_value)}频道', 'success')
        else:
            flash('状态无效', 'error')
    
    else:
        flash('无效的删除操作', 'error')
    
    return redirect(url_for('index'))

@app.route('/import_url', methods=['GET', 'POST'])
def import_from_url():
    """从URL导入播放列表"""
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        test_channels = request.form.get('test_channels', 'no') == 'yes'
        
        if not url:
            flash('URL不能为空', 'error')
            return redirect(request.url)
        
        try:
            # 下载播放列表
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # 解析M3U文件
            content = response.text
            channels = parse_m3u(content)
            
            if channels:
                # 如果选择了测试频道
                if test_channels:
                    flash(f'正在测试 {len(channels)} 个频道，这可能需要一些时间...', 'info')
                    channels = test_channels_batch(channels)
                    
                    # 统计在线和离线频道数量
                    online_count = sum(1 for c in channels if c['status'] == 'online')
                    offline_count = sum(1 for c in channels if c['status'] == 'offline')
                    error_count = sum(1 for c in channels if c['status'] == 'error')
                    
                    # 保存频道列表
                    save_channels(channels)
                    flash(f'成功从URL加载 {len(channels)} 个频道。在线: {online_count}, 离线: {offline_count}, 错误: {error_count}', 'success')
                else:
                    # 不测试，直接保存
                    save_channels(channels)
                    flash(f'成功从URL加载 {len(channels)} 个频道', 'success')
            else:
                flash('未找到任何频道', 'warning')
            
            return redirect(url_for('index'))
        
        except Exception as e:
            flash(f'从URL导入时出错: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('import_url.html')

@app.route('/api/channels')
def api_channels():
    """API: 获取所有频道"""
    channels = load_channels()
    return jsonify(channels)

@app.route('/api/channel/<int:channel_id>')
def api_channel(channel_id):
    """API: 获取特定频道信息"""
    channels = load_channels()
    
    if 0 <= channel_id < len(channels):
        return jsonify(channels[channel_id])
    else:
        return jsonify({"error": "Channel not found"}), 404

@app.route('/proxy/<path:encoded_url>')
def proxy_stream(encoded_url):
    """代理HTTP流，解决混合内容问题"""
    try:
        # 解码URL
        url = base64.b64decode(encoded_url).decode('utf-8')
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': url
        }
        
        # 转发请求
        req = requests.get(url, stream=True, headers=headers)
        
        # 获取内容类型
        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        
        # 创建响应
        def generate():
            for chunk in req.iter_content(chunk_size=1024):
                yield chunk
        
        return Response(stream_with_context(generate()), content_type=content_type)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12000, debug=True)