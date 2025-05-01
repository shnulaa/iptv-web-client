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
import hashlib
import gc
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, Response, stream_with_context
from werkzeug.utils import secure_filename

# 导入配置
from config import USERNAME, PASSWORD, MAX_CONTENT_LENGTH, UPLOAD_FOLDER, CHANNELS_FILE, PORT, DEBUG

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 用于session加密
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

def test_channel_url(url, timeout=3):
    """测试频道URL是否可访问 - 优化版本"""
    try:
        # 对于YouTube和Twitch链接，直接返回在线状态，避免请求
        if 'youtube.com' in url or 'youtu.be' in url or 'twitch.tv' in url:
            return {
                'url': url,
                'status': 'online',
                'status_code': 200
            }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 使用HEAD请求检查URL是否可访问
        try:
            response = requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
            
            # 如果HEAD请求成功，直接返回结果
            if response.status_code < 400:
                return {
                    'url': url,
                    'status': 'online',
                    'status_code': response.status_code
                }
        except requests.RequestException:
            # HEAD请求失败，尝试GET请求
            pass
        
        # 如果HEAD请求失败，尝试GET请求
        session = requests.Session()
        response = session.get(url, timeout=timeout, headers=headers, stream=True)
        
        # 只读取一小部分内容
        try:
            for chunk in response.iter_content(chunk_size=512):
                if chunk:
                    break
                # 只读取第一个块
                break
        finally:
            # 确保关闭连接
            response.close()
            session.close()
        
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
    except Exception as e:
        return {
            'url': url,
            'status': 'error',
            'error': f"未知错误: {str(e)}"
        }

def test_channels_batch(channels, max_workers=5, task_id=None):
    """批量测试多个频道URL，更加内存高效，并支持进度更新"""
    global test_tasks
    
    # 限制并发数，避免内存溢出
    max_workers = min(max_workers, 5)
    
    # 创建一个副本，避免修改原始列表
    channels_copy = []
    for channel in channels:
        channels_copy.append({
            'url': channel['url'],
            'name': channel['name'],
            'group': channel.get('group', '未分组')
        })
    
    # 分批处理，每批最多50个频道
    batch_size = 50
    total_channels = len(channels_copy)
    processed_count = 0
    
    # 创建结果字典，用于存储测试结果
    results = {}
    
    for i in range(0, total_channels, batch_size):
        batch = channels_copy[i:i+batch_size]
        urls = [channel['url'] for channel in batch]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(test_channel_url, url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    # 存储测试结果
                    results[url] = result
                    
                    # 更新频道副本的状态
                    for channel in channels_copy:
                        if channel['url'] == url:
                            channel['status'] = result['status']
                            if 'status_code' in result:
                                channel['status_code'] = result['status_code']
                            if 'error' in result:
                                channel['error'] = result['error']
                            break
                    
                    # 更新原始频道的状态
                    for channel in channels:
                        if channel['url'] == url:
                            channel['status'] = result['status']
                            if 'status_code' in result:
                                channel['status_code'] = result['status_code']
                            if 'error' in result:
                                channel['error'] = result['error']
                            break
                except Exception as e:
                    # 处理异常
                    error_result = {
                        'url': url,
                        'status': 'error',
                        'error': str(e)
                    }
                    results[url] = error_result
                    
                    # 更新频道副本的状态
                    for channel in channels_copy:
                        if channel['url'] == url:
                            channel['status'] = 'error'
                            channel['error'] = str(e)
                            break
                    
                    # 更新原始频道的状态
                    for channel in channels:
                        if channel['url'] == url:
                            channel['status'] = 'error'
                            channel['error'] = str(e)
                            break
                
                # 更新进度
                processed_count += 1
                if task_id and task_id in test_tasks:
                    test_tasks[task_id]['progress'] = processed_count
        
        # 每批处理完后，释放内存
        gc.collect()
    
    return channels_copy

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                flash('登录成功', 'success')
                return redirect(next_page)
            else:
                flash('登录成功', 'success')
                return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """注销"""
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('已注销', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
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

import threading

# 全局变量，用于存储测试任务状态
test_tasks = {}

def background_test_channels(task_id, channels_to_test, selected_group):
    """后台测试频道函数"""
    global test_tasks
    
    # 更新任务状态为进行中
    test_tasks[task_id]['status'] = 'running'
    test_tasks[task_id]['progress'] = 0
    test_tasks[task_id]['total'] = len(channels_to_test)
    
    try:
        # 测试频道
        start_time = time.time()
        
        # 获取所有频道
        all_channels = load_channels()
        
        # 创建URL到频道的映射，用于更新状态
        url_to_channel = {channel['url']: channel for channel in all_channels}
        
        # 测试频道 - 传递task_id以更新进度
        tested_channels = test_channels_batch(channels_to_test, max_workers=3, task_id=task_id)
        end_time = time.time()
        
        # 更新原始频道列表中的状态
        for channel in tested_channels:
            if channel['url'] in url_to_channel:
                url_to_channel[channel['url']]['status'] = channel.get('status', 'unknown')
                if 'status_code' in channel:
                    url_to_channel[channel['url']]['status_code'] = channel['status_code']
                if 'error' in channel:
                    url_to_channel[channel['url']]['error'] = channel['error']
        
        # 保存更新后的频道列表
        save_channels(all_channels)
        
        # 统计在线和离线频道数量
        online_count = sum(1 for c in tested_channels if c.get('status') == 'online')
        offline_count = sum(1 for c in tested_channels if c.get('status') == 'offline')
        error_count = sum(1 for c in tested_channels if c.get('status') == 'error')
        
        # 计算测试耗时
        test_time = end_time - start_time
        
        # 更新任务状态为完成
        test_tasks[task_id]['status'] = 'completed'
        test_tasks[task_id]['progress'] = len(channels_to_test)
        test_tasks[task_id]['result'] = {
            'time': test_time,
            'online': online_count,
            'offline': offline_count,
            'error': error_count,
            'group': selected_group
        }
        
        # 释放内存
        gc.collect()
        
    except Exception as e:
        # 更新任务状态为失败
        test_tasks[task_id]['status'] = 'failed'
        test_tasks[task_id]['error'] = str(e)

@app.route('/test_channels', methods=['GET', 'POST'])
@login_required
def test_channels_route():
    """测试频道是否可访问"""
    global test_tasks
    
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
        
        # 创建任务ID
        task_id = str(int(time.time()))
        
        # 初始化任务状态
        test_tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'total': len(test_channels),
            'start_time': time.time(),
            'group': selected_group
        }
        
        # 启动后台线程进行测试
        thread = threading.Thread(
            target=background_test_channels,
            args=(task_id, test_channels, selected_group)
        )
        thread.daemon = True
        thread.start()
        
        flash(f'已开始在后台测试 {len(test_channels)} 个频道，您可以继续使用其他功能。', 'info')
        
        return redirect(url_for('test_status', task_id=task_id))
    
    # 获取所有频道分组
    channels = load_channels()
    groups = sorted(list(set(channel['group'] for channel in channels)))
    
    return render_template('test_channels.html', groups=groups)

@app.route('/test_single_channel', methods=['POST'])
@login_required
def test_single_channel():
    """测试单个频道"""
    channel_id = request.form.get('channel_id')
    
    if not channel_id:
        flash('频道ID不能为空', 'error')
        return redirect(url_for('index'))
    
    try:
        channel_id = int(channel_id)
        channels = load_channels()
        
        if 0 <= channel_id < len(channels):
            channel = channels[channel_id]
            
            # 测试频道
            start_time = time.time()
            result = test_channel_url(channel['url'])
            end_time = time.time()
            
            # 更新频道状态
            channel['status'] = result['status']
            if 'status_code' in result:
                channel['status_code'] = result['status_code']
            if 'error' in result:
                channel['error'] = result['error']
            
            # 保存更新后的频道列表
            save_channels(channels)
            
            # 计算测试耗时
            test_time = end_time - start_time
            
            # 显示测试结果
            status_map = {
                'online': '在线',
                'offline': '离线',
                'error': '错误'
            }
            
            status_text = status_map.get(result['status'], result['status'])
            
            if result['status'] == 'online':
                flash(f'频道 "{channel["name"]}" 测试完成，状态: {status_text}，耗时: {test_time:.2f}秒', 'success')
            elif result['status'] == 'offline':
                flash(f'频道 "{channel["name"]}" 测试完成，状态: {status_text}，状态码: {result.get("status_code", "未知")}，耗时: {test_time:.2f}秒', 'warning')
            else:
                flash(f'频道 "{channel["name"]}" 测试完成，状态: {status_text}，错误: {result.get("error", "未知错误")}，耗时: {test_time:.2f}秒', 'danger')
        else:
            flash('频道不存在', 'error')
    except Exception as e:
        flash(f'测试频道时出错: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/test_status/<task_id>')
@login_required
def test_status(task_id):
    """查看测试任务状态"""
    global test_tasks
    
    if task_id not in test_tasks:
        flash('测试任务不存在', 'error')
        return redirect(url_for('index'))
    
    task = test_tasks[task_id]
    
    # 如果任务已完成，显示结果
    if task['status'] == 'completed':
        result = task['result']
        flash(f'测试完成，耗时 {result["time"]:.2f} 秒。在线: {result["online"]}, 离线: {result["offline"]}, 错误: {result["error"]}', 'success')
        
        # 清理任务数据（可选，保留最近的任务）
        if len(test_tasks) > 5:
            # 找到最旧的已完成任务
            oldest_task_id = None
            oldest_time = float('inf')
            for tid, t in list(test_tasks.items()):
                if t['status'] == 'completed' and t['start_time'] < oldest_time:
                    oldest_task_id = tid
                    oldest_time = t['start_time']
            
            # 删除最旧的任务
            if oldest_task_id and oldest_task_id != task_id:
                del test_tasks[oldest_task_id]
        
        return redirect(url_for('index'))
    
    # 如果任务失败，显示错误
    elif task['status'] == 'failed':
        flash(f'测试失败: {task.get("error", "未知错误")}', 'error')
        return redirect(url_for('index'))
    
    # 如果任务正在进行中，显示进度页面
    return render_template('test_status.html', task=task, task_id=task_id)

@app.route('/play/<int:channel_id>')
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def import_from_url():
    """从URL导入播放列表"""
    global test_tasks
    
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
            new_channels = parse_m3u(content)
            
            if new_channels:
                # 加载现有频道
                existing_channels = load_channels()
                
                # 合并频道列表
                for channel in new_channels:
                    existing_channels.append(channel)
                
                # 保存频道列表
                save_channels(existing_channels)
                
                # 如果选择了测试频道
                if test_channels:
                    # 创建任务ID
                    task_id = str(int(time.time()))
                    
                    # 初始化任务状态
                    test_tasks[task_id] = {
                        'status': 'pending',
                        'progress': 0,
                        'total': len(new_channels),
                        'start_time': time.time(),
                        'group': 'imported'
                    }
                    
                    # 启动后台线程进行测试
                    thread = threading.Thread(
                        target=background_test_channels,
                        args=(task_id, new_channels, 'imported')
                    )
                    thread.daemon = True
                    thread.start()
                    
                    flash(f'成功从URL加载 {len(new_channels)} 个频道。正在后台测试频道可用性...', 'success')
                    return redirect(url_for('test_status', task_id=task_id))
                else:
                    # 不测试，直接返回
                    flash(f'成功从URL加载 {len(new_channels)} 个频道', 'success')
            else:
                flash('未找到任何频道', 'warning')
            
            return redirect(url_for('index'))
        
        except Exception as e:
            flash(f'从URL导入时出错: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('import_url.html')

@app.route('/api/channels')
@login_required
def api_channels():
    """API: 获取所有频道"""
    channels = load_channels()
    return jsonify(channels)

@app.route('/api/channel/<int:channel_id>')
@login_required
def api_channel(channel_id):
    """API: 获取特定频道信息"""
    channels = load_channels()
    
    if 0 <= channel_id < len(channels):
        return jsonify(channels[channel_id])
    else:
        return jsonify({"error": "Channel not found"}), 404

@app.route('/proxy/<path:encoded_url>')
@login_required
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
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)