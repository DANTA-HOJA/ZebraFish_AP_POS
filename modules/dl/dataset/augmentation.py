from imgaug import augmenters as iaa
# -----------------------------------------------------------------------------/


def crop_base_size(width, height):
    """
    """
    return iaa.CropToFixedSize(width=width, height=height,
                               position="center")
    # -------------------------------------------------------------------------/



def dynamic_crop(size:int) -> iaa.Sequential:
    """ rotate -> random crop -> return
    """
    transform = iaa.Sequential([
        iaa.Sometimes(0.5, 
            iaa.Affine(rotate=(-25, 25)),
        ),
        iaa.CropToFixedSize(width=size, height=size),
        iaa.GammaContrast((0.5, 2.0)), # one line for ablation test
    ])
    
    return transform
    # -------------------------------------------------------------------------/



def composite_aug() -> iaa.Sequential:
    """
    """
    transform = iaa.Sequential([
        # iaa.Sometimes(0.5, iaa.Affine(
        #     # scale={"x": (0.8, 1.2), "y": (0.8, 1.2)},
        #     # translate_percent={"x": (-0.2, 0.2), "y": (-0.2, 0.2)},
        #     rotate=(-25, 25),
        #     shear=(-8, 8)
        # )),
        # iaa.CropToFixedSize(width=512, height=512),
        iaa.Fliplr(p=0.5),
        iaa.Flipud(p=0.5),
        iaa.Sequential([
            iaa.Sometimes(0.5, [
                iaa.WithChannels([0, 1], iaa.Clouds()), # ch_B, ch_G
                # iaa.Sometimes(0.3, iaa.Cartoon()),
                # iaa.GammaContrast((0.5, 2.0)), # 可能會調得更暗，暫時取消
                iaa.OneOf([
                    iaa.GaussianBlur(sigma=(0, 3.0)), # blur images with a sigma of 0 to 3.0
                    iaa.Sharpen(alpha=0.5)
                ])
            ]), 
        ], random_order=True),
        iaa.Dropout2d(p=0.2, nb_keep_channels=2),
    ])
    
    return transform
    # -------------------------------------------------------------------------/