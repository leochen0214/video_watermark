import random
from pathlib import Path
from PIL import Image
from algorithm.firekepper import Watermark as fwatermark


def encodewatermark_image(frame_processed_dir:Path, image:Path, watermark_image:Path, seed):
    """

    :param image:输入图片Path
    :param watermark_image: 输入水印图片Path
    :param seed: 水印参数
    :return:水印尺寸
    """
    image_name = Path(image).name
    bwm1 = fwatermark(seed[0], seed[1], seed[2])
    bwm1.read_ori_img(image)
    bwm1.read_wm(watermark_image)
    bwm1.embed(f"{frame_processed_dir}/{image_name}")
    # 打开图片文件
    img = Image.open(str(watermark_image))

    # 获取图片分辨率
    width, height = img.size
    ren=[width,height]
    return ren


def decodewatermark_image(input,
                          recoverresult_dir,
                          shape,
                          seed):
    result_file = recoverresult_dir.joinpath((str(random.randint(1, 9999999999)) + "wm_" + input.name))
    bwm1 = fwatermark(int(seed[0]), int(seed[1]), int(seed[2]), wm_shape=(int(shape[0]), int(shape[1])))
    bwm1.extract(input, result_file)
