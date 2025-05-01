// 主JavaScript文件

// 在页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化Bootstrap提示工具
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // 初始化Bootstrap弹出框
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // 自动关闭警告框
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // 检测图片加载错误并替换为默认图标
    document.querySelectorAll('.channel-logo').forEach(function(img) {
        img.addEventListener('error', function() {
            // 创建替代元素
            var placeholder = document.createElement('div');
            placeholder.className = 'channel-logo-placeholder d-flex align-items-center justify-content-center bg-light';
            placeholder.innerHTML = '<i class="bi bi-tv fs-3"></i>';
            
            // 替换图片
            img.parentNode.replaceChild(placeholder, img);
        });
    });
});