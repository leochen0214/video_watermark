import logging
import asyncio
import time
from typing import Dict

from video_watermark import common
from video_watermark.tool import BaiduNetDisk
from video_watermark.tool import wechat

SENT_TEXT = '已发送'


def main():
    common.init()
    asyncio.run(batch_share(common.get_person_name_mappings()))


async def batch_share(person_contact_mappings: Dict[str, str]):
    """
       批量分享处理主函数

       功能概述：
       1. 根据人员-联系人映射关系，为每个人员生成百度网盘分享链接
       2. 通过微信将分享链接发送给对应的联系人
       3. 管理分享状态，避免重复生成和发送

       处理逻辑：
       - 检查人员是否已有分享链接（已发送或已生成未发送）
       - 为没有分享链接的人员生成新的分享链接
       - 对所有人员尝试发送微信消息
       - 成功发送后标记文件状态

       param：
        person_contact_mappings: 人员姓名到微信联系人的映射字典, eg: {person : contact_name}

       状态文件说明：
       - {person}.txt: 已生成分享链接但未发送
       - {person}_已发送.txt: 已成功发送分享链接
       """
    # {person}->contact_name mappings

    if not person_contact_mappings:
        logging.info('No person name mappings found')
        return
    # {person}->是否已经发送给联系人 mappings
    person_sent_mappings = _get_person_sent_mappings()
    # 待生成分享链接的人员集合
    person_share_link_mappings = await gen_share_links(
        _get_pending_to_gen_share_link_persons(person_contact_mappings, person_sent_mappings))

    for person, contact_name in person_contact_mappings.items():
        if person in person_sent_mappings:
            if person_sent_mappings[person] is True:
                logging.info(f'已成功发送过分享链接，跳过, person: {person}, contact_name: {contact_name}')
            else:
                logging.info(f'已经生成分享链接,但还未发送给联系人, person: {person}, contact_name: {contact_name}')
                share_link = common.read_content(_get_share_link_file(person))
                _do_send_wechat(person, contact_name, share_link)
        else:
            share_link = person_share_link_mappings.get(person)
            _do_send_wechat(person, contact_name, share_link)


async def gen_share_links(persons):
    validity_period = common.get_validity_period()
    res = {}
    async with BaiduNetDisk() as baidu:
        for person in persons:
            share_link = await share_for_person(baidu, person, validity_period)
            res[person] = share_link
    return res


def _do_send_wechat(person, contact_name, share_link):
    if not contact_name:
        logging.info(f'联系方式为空,无法发送share_link, person: {person}')
        return
    if not share_link:
        logging.info(f'分享链接为空，无法发送, person: {person}')
        return
    try:
        success = wechat.send_wechat_message(contact_name, share_link)
    except Exception as e:
        logging.error(f'send_wechat_message error, str{e}')
        success = False
    if success:
        _rename(person)
        logging.info(f'发送分享链接成功, person: {person}, wechat: {contact_name}')
    else:
        logging.info(f'发送分享链接失败, person: {person}, wechat: {contact_name}')


def _get_person_sent_mappings():
    file_filter = lambda f: (f.is_file()
                             and not f.name.startswith('.')
                             and not f.name.startswith('output')
                             and f.suffix in ['.txt'])
    files = common.get_files(_get_share_storage_dir(), recursive=False, file_filter=file_filter)
    res = {}
    for f in files:
        name = f.stem
        if SENT_TEXT in name:
            person = name.split('_')[0]
            res[person] = True
        else:
            res[name] = False
    return res


def _get_pending_to_gen_share_link_persons(person_contact_mappings, person_sent_mappings):
    return set(person_contact_mappings.keys()) - set(person_sent_mappings.keys())


async def share_for_person(baidu, person, validity_period):
    try:
        logging.info(f"开始为人员生成分享链接： {person}")
        start = time.time()
        share_link = await _do_share(person, validity_period, baidu)
        if share_link:
            filename = _get_share_link_file(person)
            common.create_dir(filename.parent)
            common.write(filename, share_link)
            logging.info(f'分享链接内容写入文件成功: {filename}')
        else:
            logging.info(f'分享链接生成失败: {person}')
        end = time.time()
        logging.info(f"为人员生成分享结束: {person}, costs {end - start:.2f} seconds")
        return share_link
    except Exception as e:
        logging.error(f"为人员生成分享链接异常 {person} 数据失败: {str(e)}", exc_info=True)
        return None


async def _do_share(person: str, validity_period, baidu: BaiduNetDisk):
    course_name = common.get_current_course_name()
    remote_dir = f"{common.get_root_remote_dir()}/videos/{person}/{course_name}"
    return await baidu.share(remote_dir, validity_period)


def _get_share_storage_dir():
    return common.get_baidu_dir().joinpath('persons')


def _get_share_link_file(person):
    return _get_share_storage_dir().joinpath(f'{person}.txt')


def _rename(person):
    share_storage_dir = _get_share_storage_dir()
    # 构造原始文件路径
    original_file_path = _get_share_link_file(person)
    if original_file_path.exists():
        # 构造新文件路径
        new_file_path = share_storage_dir.joinpath(f'{person}_{SENT_TEXT}.txt')
        # 重命名文件
        original_file_path.rename(new_file_path)


if __name__ == '__main__':
    main()