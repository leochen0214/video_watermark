#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信自动发送消息脚本
使用AppleScript控制微信发送中文消息给指定联系人
"""

import subprocess
import time


def send_wechat_message(contact_name, message):
    """
    发送微信消息给指定联系人

    Args:
        contact_name (str): 联系人名称（支持中文）
        message (str): 要发送的消息内容（支持中文）
    """

    applescript = f'''
    -- 设置剪贴板的函数
    on setClipboard(theText)
        set the clipboard to theText
    end setClipboard

    tell application "WeChat"
        activate
        delay 1

        tell application "System Events"
            tell process "WeChat"
                -- 第一步：搜索联系人
                my setClipboard("{contact_name}")
                delay 0.3

                -- 打开搜索框
                key code 3 using command down  -- Cmd+F 打开搜索
                delay 0.8

                -- 清空搜索框并粘贴联系人名称
                key code 0 using command down  -- Cmd+A 全选
                delay 0.3
                key code 51  -- Delete键清空
                delay 0.3
                key code 9 using command down  -- Cmd+V 粘贴联系人名称
                delay 1.5

                -- 第二步：选中搜索结果进入聊天
                key code 36   -- 回车键，Return键进入聊天窗口
                delay 2       -- 等待聊天窗口完全加载

                -- 第三步：多次尝试确保焦点在输入框（只测试不发送）
                set focusAttempts to 0
                set inputReady to false

                repeat while focusAttempts < 10 and not inputReady
                    -- 尝试不同的定位方法
                    if focusAttempts = 0 then
                        -- 方法1: 直接点击输入框区域（窗口底部偏左）
                        try
                            set winBounds to bounds of window 1
                            set clickX to (item 1 of winBounds) + 200  -- 窗口左边缘往右200像素
                            set clickY to (item 4 of winBounds) - 50   -- 窗口底部往上50像素
                            click at {{clickX, clickY}}
                        end try
                    else if focusAttempts = 1 then
                        -- 方法2: 点击输入框中心区域
                        try
                            set winBounds to bounds of window 1
                            set clickX to ((item 1 of winBounds) + (item 3 of winBounds)) / 2
                            set clickY to (item 4 of winBounds) - 80
                            click at {{clickX, clickY}}
                        end try
                    else if focusAttempts = 2 then
                        -- 方法3: Tab键定位
                        key code 48  -- Tab键
                    else if focusAttempts = 3 then
                        -- 方法4: Shift+Tab反向定位
                        key code 48 using shift down
                    else if focusAttempts = 4 then
                        -- 方法5: ESC键清除当前焦点，然后Tab
                        key code 53  -- ESC键
                        delay 0.3
                        key code 48  -- Tab键
                    else if focusAttempts = 5 then
                        -- 方法6: 点击更靠近输入区域的位置
                        try
                            set winBounds to bounds of window 1
                            set clickX to (item 1 of winBounds) + 150
                            set clickY to (item 4 of winBounds) - 30
                            click at {{clickX, clickY}}
                        end try
                    else if focusAttempts = 6 then
                        -- 方法7: 多次Tab键
                        key code 48  -- Tab键
                        delay 0.3
                        key code 48  -- 再次Tab键
                    else if focusAttempts = 7 then
                        -- 方法8: 点击输入框左侧区域
                        try
                            set winBounds to bounds of window 1
                            set clickX to (item 1 of winBounds) + 100
                            set clickY to (item 4 of winBounds) - 60
                            click at {{clickX, clickY}}
                        end try
                    else
                        -- 方法9-10: 尝试其他Tab组合
                        repeat 2 times
                            key code 48
                            delay 0.2
                        end repeat
                    end if

                    delay 0.8

                    -- 测试输入框是否可用（不按回车，不发送消息）
                    try
                        -- 输入一个测试字符（不按回车）
                        keystroke "a"
                        delay 0.3

                        -- 检查是否成功输入
                        key code 0 using command down  -- Cmd+A 全选
                        delay 0.3
                        key code 8 using command down  -- Cmd+C 复制
                        delay 0.3
                        set testContent to the clipboard as text

                        -- 如果复制到了"a"，说明输入框可用
                        if testContent contains "a" then
                            -- 立即清空测试字符（重要：不要按回车）
                            key code 0 using command down  -- 全选
                            delay 0.2
                            key code 51  -- Delete删除（不是回车）
                            delay 0.3
                            set inputReady to true
                        else
                            set inputReady to false
                        end if
                    on error
                        set inputReady to false
                    end try

                    set focusAttempts to focusAttempts + 1
                end repeat

                if not inputReady then
                    return "FOCUS_FAILED"
                end if

                -- 第四步：发送真正的消息（只发送一次，不重试）
                if not inputReady then
                    return "FOCUS_FAILED"
                end if

                -- 发送消息
                my setClipboard("{message}")
                delay 0.5

                try
                    -- 清空输入框并粘贴消息
                    key code 0 using command down  -- Cmd+A 全选
                    delay 0.3
                    key code 51  -- Delete清空
                    delay 0.3
                    key code 9 using command down  -- Cmd+V 粘贴消息
                    delay 1

                    -- 发送消息（只发送一次，无论结果如何）
                    key code 36  -- Return键发送
                    delay 3  -- 给足够时间让消息发送

                    -- 简单返回成功，不再检查输入框状态
                    -- 因为检查输入框状态可能不准确，而且消息实际上已经发送了
                    return "SUCCESS"

                on error
                    -- 即使出现错误，消息可能已经发送，返回成功避免重试
                    return "SUCCESS"
                end try
            end tell
        end tell
    end tell
    '''

    try:
        # 执行完整的AppleScript
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30  # 添加超时设置
        )

        print(f"脚本执行结果: {result.stdout.strip()}")
        errorMsg = result.stderr.strip()
        print(f"错误信息: {errorMsg}")

        if "不允许" in errorMsg or "not allowed" in errorMsg:
            request_permission()
            return False

        # 简化的成功判断逻辑 - 避免因验证问题导致重复发送
        if "SUCCESS" in result.stdout:
            print(f"✅ 消息已发送给 {contact_name}")
            return True
        elif "FOCUS_FAILED" in result.stdout:
            print(f"❌ 无法定位到输入框")
            return False
        elif result.returncode != 0 and result.stderr:
            print(f"❌ AppleScript执行失败: {result.stderr}")
            return False
        else:
            # 保守判断：如果没有明确失败信息，认为可能成功了
            print(f"✅ 消息可能已发送给 {contact_name}")
            return True

    except subprocess.TimeoutExpired:
        print(f"❌ 操作超时，发送失败")
        return False
    except Exception as e:
        print(f"❌ 执行出错: {str(e)}")
        return False


def check_wechat_running():
    """检查微信是否正在运行"""
    try:
        result = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to get name of processes'],
            capture_output=True,
            text=True
        )
        return "WeChat" in result.stdout
    except:
        return False


def open_wechat():
    """打开微信应用"""
    try:
        subprocess.run(['open', '-a', 'WeChat'], check=True)
        print("正在启动微信...")
        time.sleep(3)  # 等待微信启动
        return True
    except:
        print("❌ 无法启动微信，请确保已安装微信应用")
        return False


def request_permission():
    """请求用户授予必要的权限"""
    print("❌ 需要授予辅助功能权限才能控制微信")
    print("请按以下步骤操作：")
    print("1. 打开系统设置 > 隐私与安全性 > 辅助功能")
    print("2. 解锁设置（点击右下角锁图标）")
    print("3. 找到并勾选'终端'、‘iTerm’、'Python'和'osascript'")
    print("4. 重新运行此脚本")

    # 打开系统设置中的辅助功能页面
    subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])
    return False
