from PIL import ImageFont, Image, ImageDraw, ImageColor
import qrcode
from ..common import directories
from ..common import video_operations
from ..common import get_font_file
from ..common import create_dir


def makeimage(text, filename, font_size=24, bg_color='black', font_color='white', spacing=4, padding=5, align = 'center'):
    font = ImageFont.truetype(get_font_file(), size=font_size)
    image_size = _calculate_image_size(text, font_size, spacing=spacing, padding=padding)
    w = image_size[0]
    h = image_size[1]
    text_width = image_size[2]
    text_height = image_size[3]
    # 创建一个具有透明背景的图像, 0表示完全透明背景    
    image = Image.new("RGBA", (w, h), _to_rgba(bg_color, 0))

    # 创建 ImageDraw 对象  
    draw = ImageDraw.Draw(image)  

    # 计算文本尺寸，并得到居中位置  
    x = (w - text_width) / 2  # 水平居中  
    y = (h - text_height) / 2  # 垂直居中  

    #半透明文本颜色
    text_color = _to_rgba(font_color, 128)

    # 绘制多行文本  
    draw.multiline_text((x, y), text, font=font, fill=text_color, spacing=spacing, align=align)
    
    # 保存图像 
    image.save(video_operations.get_logo_watermark_image(filename))

def genqrcode(text, filename, pix=4):
    # 设置相关参数，生成一个二维码对象（QRCode对象）
    qr_obj = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=pix,
        border=0,
    )
    # 设置二维码信息内容
    qr_obj.add_data(str(text))
    # 设置二维码图形的大小
    # 当参数fit为True时，二维码图形根据信息内容大小调节到合适尺寸，
    # 当参数fit为False时，二维码图形不会调节，如果信息内容过大将报错
    qr_obj.make(fit=True)
    # 生成二维码图像，设置二维码颜色为黑色，背景色为白色
    qr_img = qr_obj.make_image(fill_color='black', back_color='white')
    # 显示二维码
    #qr_img.show()
    # 保存二维码图片
    qr_img.save(video_operations.get_qrcode_image(filename))


def _to_rgba(color, alpha):
    # 获取 RGBA 值  
    rgb = ImageColor.getrgb(color)  # 返回 RGB 值  
    text_color = (*rgb, alpha)  # 将 RGB 和 alpha 值组合成 RGBA, 输出 (255, 0, 0, 128)  
    return text_color

def _calculate_image_size(text, font_size, spacing=4, padding=0):
    font = ImageFont.truetype(get_font_file(), size=font_size)
    # 创建一个临时的图像以便计算  
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1))) 
    # 文本宽度、高度
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)  
    x0, y0, x1, y1 = bbox  
    text_width = x1 - x0  
    text_height = y1 - y0  
    # 图片宽度、高度
    w = text_width + 2 * padding
    h = text_height + 2 * padding
    return [w, h, text_width, text_height]
