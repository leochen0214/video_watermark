import asyncio
import logging
import os
import re
from urllib.parse import quote
from pathlib import Path

from playwright.async_api import async_playwright

from video_watermark import common


class BaiduNetDisk:
    def __init__(self):
        # 配置文件路径
        self.baidu_dir = common.get_baidu_dir()
        common.create_dir(self.baidu_dir)
        self.storage_state_path = f'{self.baidu_dir}/baidu_netdisk_state.json'
        self.browser = None
        self.context = None
        self.page = None
        self.context_was_new = False

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            slow_mo=300,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )

        # 尝试加载已有登录状态
        self.context = await self._load_login_state()
        if self.context is None:
            self.context = await self.browser.new_context(
                viewport={"width": 1200, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await self._set_webdriver()
            self.context_was_new = True
            logging.info('创建新的浏览器上下文')
        else:
            logging.info('加载了已保存的登录状态')

        self.page = await self.context.new_page()
        await self._print_webdriver()

    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def ensure_login(self):
        """确保登录状态有效"""
        logging.info('开始检查登录状态')
        await self._print_webdriver()

        # 先检查当前页面URL
        current_url = self.page.url
        logging.info(f"当前页面URL: {current_url}")

        # 如果已经在主页，直接返回成功
        if self._is_main_url(current_url):
            logging.info("已在网盘主页，登录状态有效")
            return True

        # 如果不在主页，尝试导航
        try:
            await self.page.goto("https://pan.baidu.com/", wait_until="networkidle", timeout=10000)
            await self.page.wait_for_timeout(3000)

            current_url = self.page.url
            logging.info(f"导航后的页面URL: {current_url}")

            if self._is_main_url(current_url):
                logging.info("页面已自动跳转到网盘主页，登录状态有效")
                return True

        except Exception as nav_error:
            logging.info(f"导航失败: {nav_error}")
            if self._is_main_url(self.page.url):
                logging.info("虽然导航失败，但当前页面仍然有效")
                return True

        logging.info("页面未跳转到主页，需要进行登录")

        # 需要登录的情况下才执行以下代码
        try:
            await self.page.wait_for_timeout(2000)
            await self._screenshot('before_login_click.png')

            login_locators = [
                self.page.get_by_role("button", name="去登录"),
                self.page.get_by_role("button", name="登录"),
                self.page.get_by_role("link", name="去登录"),
                self.page.get_by_role("link", name="登录"),
                self.page.get_by_text("去登录"),
                self.page.get_by_text("登录"),
                self.page.get_by_label("去登录"),
                self.page.get_by_label("登录"),
                self.page.get_by_title("去登录"),
                self.page.get_by_title("登录"),
            ]

            login_clicked = False
            for i, locator in enumerate(login_locators):
                try:
                    locator_desc = str(locator)
                    logging.info(f"尝试定位器 {i + 1}/{len(login_locators)}: {locator_desc}")

                    try:
                        await locator.wait_for(state="attached", timeout=2000)
                    except:
                        logging.info(f"定位器未找到元素: {locator_desc}")
                        continue

                    if await locator.is_visible():
                        logging.info(f"找到可见元素: {locator_desc}")
                        try:
                            await locator.click(timeout=5000)
                            login_clicked = True
                            logging.info(f"成功点击登录按钮: {locator_desc}")
                            await self.page.wait_for_timeout(2000)
                            break
                        except Exception as click_error:
                            logging.error(f"点击失败: {click_error}")
                            continue
                    else:
                        logging.info(f"元素不可见: {locator_desc}")

                except Exception as locator_error:
                    logging.error(f"定位器异常: {locator_error}")
                    continue

            if not login_clicked:
                logging.info("所有方法都失败，可能已在登录页面或需要手动操作")
                await self._screenshot('login_button_not_found.png')

            logging.info("请使用百度APP扫码登录...")
            return await self._wait_for_login_complete()

        except Exception as login_error:
            logging.error(f"登录过程出错: {login_error}")
            await self._screenshot('login_process_error.png')
            return False

    async def get_share_content(self, filename, period=7):
        """分享指定文件"""
        p = Path(filename)
        file_path = p.parent.as_posix()
        file_name = p.name
        sep = '' if file_path == '/' else '/'
        logging.info(f"正在分享文件: {file_path}{sep}{file_name}")
        sleep_time = 3000 if self.context_was_new else 1000
        await self.page.wait_for_timeout(sleep_time)

        try:
            await self._screenshot('before_share.png')

            if not await self._navigate_to_path(file_path):
                return None

            await self.page.wait_for_timeout(2000)
            await asyncio.sleep(2)

            # 关闭云U盘提示框
            await self._close_popup_dialog()

            # 右键点击文件
            found = await self._find_file_and_right_click(file_name, '.wp-s-pan-table__body.mouse-choose-list')
            if not found:
                return None

            await self.page.wait_for_timeout(2000)
            logging.info("已右键点击文件，查找分享选项...")
            await self._screenshot('right_click_menu.png')

            # 查找并点击分享选项
            share_locators = [
                self.page.get_by_role("button", name="分享"),
                self.page.get_by_role("menuitem", name="分享"),
                self.page.get_by_text("分享"),
            ]

            share_clicked = False
            for i, locator in enumerate(share_locators):
                try:
                    locator_desc = str(locator)
                    logging.info(f"尝试分享选项 {i + 1}/{len(share_locators)}: {locator_desc}")
                    await locator.wait_for(state="visible", timeout=3000)
                    await locator.click(timeout=3000)
                    share_clicked = True
                    logging.info(f"成功点击分享选项: {locator_desc}")
                    break
                except Exception as share_error:
                    logging.info(f"分享选项 {i + 1} 失败: {share_error}")
                    continue

            if not share_clicked:
                logging.info("未找到分享选项")
                await self._screenshot('share_option_not_found.png')
                return None

            # await self.page.wait_for_timeout(3000)

            try:
                link_share_tab = self.page.get_by_text("链接分享").first
                await link_share_tab.wait_for(state="visible", timeout=2000)
                await link_share_tab.click()
                logging.info("已切换到链接分享tab")
            except:
                logging.info("未找到链接分享tab，可能已经在正确的tab中")

            await self.page.wait_for_timeout(1000)

            logging.info(f"设置{period}天有效期...")
            try:
                period_option = self.page.get_by_text(f"{period}天").first
                await period_option.wait_for(state="visible", timeout=3000)
                await period_option.click()
                logging.info(f"成功选择{period}天有效期")
            except Exception as period_error:
                logging.error(f"设置有效期失败: {period_error}")

            await self.page.wait_for_timeout(1000)
            await self._screenshot('before_copy_link.png')

            logging.info("准备复制链接...")
            copy_link_selectors = [
                self.page.get_by_text("复制链接"),
                self.page.locator('button:has-text("复制链接")'),
                self.page.get_by_role("button", name="复制链接"),
                self.page.get_by_role("button", name=re.compile("复制链接")),
                self.page.get_by_text("复制"),
                self.page.locator('.copy-link-btn'),
                self.page.locator('button[data-testid*="copy"]'),
                self.page.locator('button:has-text("复制")'),
            ]

            copy_clicked = False
            for i, locator in enumerate(copy_link_selectors):
                try:
                    logging.info(f"尝试复制按钮 {i + 1}/{len(copy_link_selectors)}")
                    await locator.wait_for(state="visible", timeout=3000)
                    await locator.click()
                    copy_clicked = True
                    logging.info("成功点击复制链接按钮")
                    await self.page.wait_for_timeout(3000)
                    break
                except Exception as copy_error:
                    logging.error(f"复制按钮 {i + 1} 失败: {copy_error}")
                    continue

            if not copy_clicked:
                logging.info("未找到复制链接按钮")
                await self._screenshot('copy_button_not_found.png')
                return None

            logging.info("尝试获取复制的链接...")
            shared_link = await self._get_share_link()
            await self._close_share_dialog(file_name)
            await self._screenshot('share_operation_completed.png')
            return shared_link
        except Exception as e:
            logging.error(f"分享文件失败: {e}")
            await self._screenshot('share_error.png')
            return None

    async def _get_share_link(self):
        shared_link = None
        try:
            await self.page.wait_for_timeout(1000)
            div = await self.page.wait_for_selector('.copy-link-text')
            shared_link = await div.text_content()
            if shared_link:
                logging.info('shared_link结果')
                logging.info(shared_link)
            else:
                logging.info("未能获取到分享链接，但分享操作可能已完成")
                await self._screenshot('share_completed_no_link.png')
        except Exception as get_link_error:
            logging.error(f"获取分享链接失败: {get_link_error}")
        return shared_link

    async def _close_share_dialog(self, file_name):
        try:
            logging.info("关闭分享对话框...")
            dialog = self.page.get_by_role("dialog", name=f"分享文件(夹):{file_name}")
            close_button = dialog.get_by_role("button", name="Close")
            await close_button.click()
            logging.info("成功关闭分享对话框")
        except Exception as e:
            logging.info(f'关闭分享对话框异常, {e}')

    async def _close_popup_dialog(self):
        """close popup dialog"""
        try:
            bubble = self.page.locator(':has-text("您的云U盘")')
            if await bubble.count() > 0:
                logging.info("检测到云U盘提示框，正在关闭...")
                close_btn = bubble.locator('.wp-s-aside-nav-bubble-close')
                await close_btn.click()
                logging.info("提示框已关闭")
            else:
                logging.info("未检测到云U盘提示框")
        except Exception as e:
            logging.info('测到云U盘提示框失败', e)

    async def share(self, filename, period=7):
        """执行分享操作"""
        login_result = await self.ensure_login()
        if not login_result:
            logging.info("登录失败，退出程序")
            return None

        if self.context_was_new and self._is_main_url(self.page.url):
            logging.info("检测到新登录成功，保存登录状态...")
            await self._save_login_state()

        content = await self.get_share_content(filename, period=period)
        if content:
            logging.info("文件分享操作完成")
        else:
            logging.info("文件分享操作失败")
        return content

    async def _screenshot(self, image_name, full_page=False):
        await self.page.screenshot(path=f"{common.get_screenshot_dir()}/{image_name}", full_page=full_page)

    async def _print_webdriver(self):
        logging.info(f"webdriver: {await self.page.evaluate('navigator.webdriver')}")

    async def _is_login_success(self):
        """检查登录状态"""
        try:
            current_url = self.page.url
            if self._is_main_url(current_url):
                logging.info(f"URL已跳转到主页: {current_url}")
                return True
            return False
        except Exception as e:
            logging.info(f"登录状态检查出错: {e}")
            return False

    async def _wait_for_login_complete(self):
        """等待登录完成"""
        try:
            logging.info("等待登录完成...")
            for i in range(60):
                await self.page.wait_for_timeout(1000)
                if await self._is_login_success():
                    logging.info(f"登录成功！耗时: {i + 1}秒")
                    return True
                if (i + 1) % 5 == 0:
                    logging.info(f"等待登录中... ({i + 1}/60秒)")
                    await self._screenshot(f'login_wait_{i + 1}s.png')
            logging.info("登录等待超时")
            await self._screenshot('login_timeout.png')
            return False
        except Exception as e:
            logging.error(f"等待登录过程出错: {e}")
            await self._screenshot('login_wait_error.png')
            return False

    async def _save_login_state(self):
        """保存登录状态"""
        try:
            await self.context.storage_state(path=self.storage_state_path)
            logging.info("登录状态已保存")
        except Exception as e:
            logging.error(f"保存登录状态失败: {e}")

    async def _load_login_state(self):
        """加载登录状态"""
        if os.path.exists(self.storage_state_path):
            try:
                context = await self.browser.new_context(
                    storage_state=self.storage_state_path,
                    viewport={"width": 1200, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                await self._set_webdriver(context)
                return context
            except Exception as e:
                logging.error(f"加载登录状态失败: {e}")
                common.delete_file(self.storage_state_path)
                return None
        return None

    async def _navigate_to_path(self, file_path):
        """导航到指定路径"""
        if not file_path or file_path == "/":
            return True
        try:
            goto_page = f'https://pan.baidu.com/disk/main#/index?category=all&path={quote(file_path)}'
            print(goto_page)
            await self.page.goto(goto_page)
            return True
        except Exception as e:
            logging.error(f"导航路径失败: {e}")
            return False

    async def _find_file_and_right_click(self, target_filename, container_selector=None):
        """在页面中查找文件并右键点击"""
        max_scroll_attempts = 30
        scroll_step = 300
        scroll_delay = 0.5

        locator_strategies = [
            lambda: self.page.get_by_title(target_filename),
            lambda: self.page.get_by_text(target_filename),
            lambda: self.page.locator(f'[title="{target_filename}"]'),
            lambda: self.page.locator(f'[data-filename="{target_filename}"]'),
            lambda: self.page.locator(f'text=/{re.escape(target_filename)}/i')
        ]

        if container_selector:
            scroll_container = self.page.locator(container_selector)
            if await scroll_container.count() == 0:
                logging.info(f"错误：未找到滚动容器 {container_selector}")
                return False
            else:
                logging.info(f'{container_selector} 是可以滚动的')
        else:
            scroll_container = None

        async def try_find_file():
            for i, strategy in enumerate(locator_strategies):
                try:
                    locator = strategy()
                    if await locator.count() > 0:
                        first_match = locator.first
                        if await first_match.is_visible():
                            logging.info(f'在第{i + 1}个locator, 找到了目标文件: {target_filename}')
                            return first_match
                except Exception as e:
                    continue
            return None

        for attempt in range(max_scroll_attempts):
            file_element = await try_find_file()
            if file_element:
                await file_element.scroll_into_view_if_needed()
                await file_element.click(button="right")
                logging.info(f"成功右键点击文件: {target_filename}")
                return True

            if scroll_container:
                current_pos = await scroll_container.evaluate("el => el.scrollTop")
                max_pos = await scroll_container.evaluate("el => el.scrollHeight - el.clientHeight")

                if current_pos >= max_pos:
                    logging.info("已滚动到容器底部")
                    break

                await scroll_container.evaluate(f"(el) => {{ el.scrollTop += {scroll_step}; }}")
            else:
                current_pos = await self.page.evaluate("window.pageYOffset || document.documentElement.scrollTop")
                page_height = await self.page.evaluate("document.body.scrollHeight")
                viewport_height = await self.page.evaluate("window.innerHeight")

                if current_pos + viewport_height >= page_height:
                    logging.info("已滚动到页面底部")
                    break

                await self.page.evaluate(f"window.scrollBy(0, {scroll_step})")
                await self.page.mouse.wheel(0, scroll_step)

            await asyncio.sleep(scroll_delay)

            if attempt % 5 == 0:
                await self._screenshot(f'scroll_debug_{attempt}.png')

        logging.info(f"未找到文件: {target_filename} (尝试次数: {max_scroll_attempts})")
        return False

    async def _set_webdriver(self, context=None):
        """设置webdriver反检测"""
        ctx = context or self.context
        await ctx.add_init_script("""
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)

    def _is_main_url(self, current_url: str) -> bool:
        return "/disk/main" in current_url or "/disk/home" in current_url


# 示例用法
async def main():
    common.init()
    async with BaiduNetDisk() as netdisk:
        s = await netdisk.share('/front_end', period=30)
        print(s)


if __name__ == "__main__":
    asyncio.run(main())
