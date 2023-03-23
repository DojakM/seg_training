import torch
import torch.nn as nn
from models.model_components import UnetConv, UnetUp, SPTTo, SPTBack, Context, Localization
from models.unet_super import UnetSuper
from utils import weights_init


class Unet(UnetSuper):
    def __init__(self, len_test_set, hparams, input_channels, is_deconv=True,
                 is_batchnorm=True, on_gpu=False, **kwargs):
        super().__init__(len_test_set=len_test_set, hparams=hparams, **kwargs)
        self.in_channels = input_channels
        self.is_deconv = is_deconv
        self.is_batchnorm = is_batchnorm
        self.input = input_channels
        filters = [32, 64, 128, 256]
        self.conv1 = UnetConv(self.in_channels, filters[0], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.conv2 = UnetConv(filters[0], filters[1], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.conv3 = UnetConv(filters[1], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.center = UnetConv(filters[2], filters[3], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        # upsampling
        self.up_concat3 = UnetUp(filters[3], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.up_concat2 = UnetUp(filters[2], filters[1], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.up_concat1 = UnetUp(filters[1], filters[0], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        # final conv (without any concat)
        self.final = nn.Conv2d(filters[0], kwargs["num_classes"], 1)
        if on_gpu:
            self.conv1.cuda()
            self.conv2.cuda()
            self.conv3.cuda()
            self.center.cuda()
            self.up_concat3.cuda()
            self.up_concat2.cuda()
            self.up_concat1.cuda()
            self.final.cuda()
        self.apply(weights_init)

    def forward(self, inputs):
        maxpool = nn.MaxPool2d(kernel_size=2)
        conv1 = self.conv1(inputs)  # 16*256*256
        maxpool1 = maxpool(conv1)  # 16*128*128

        conv2 = self.conv2(maxpool1)  # 32*128*128
        maxpool2 = maxpool(conv2)  # 32*64*64

        conv3 = self.conv3(maxpool2)  # 64*64*64
        maxpool3 = maxpool(conv3)  # 64*32*32

        center = self.center(maxpool3)

        up3 = self.up_concat3(center, conv3)  # 64*64*64
        up2 = self.up_concat2(up3, conv2)  # 32*128*128
        up1 = self.up_concat1(up2, conv1)  # 16*256*256

        final = self.final(up1)
        finalize = nn.functional.softmax(final, dim=1)
        return finalize


    def print(self, args: torch.Tensor) -> None:
        print(args)

#### ==== model with spatial transformer ==== ####
class RTUnet(UnetSuper):
        def __init__(self, len_test_set, hparams, input_channels, is_deconv=True,
                     is_batchnorm=True, on_gpu=False, **kwargs):
            super().__init__(len_test_set=len_test_set, hparams=hparams, **kwargs)
            self.in_channels = input_channels
            self.is_deconv = is_deconv
            self.is_batchnorm = is_batchnorm
            self.input = input_channels
            filters = [8, 16, 32, 64]

            self.conv1 = SPTTo(self.in_channels, filters[0], gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            self.conv2 = UnetConv(filters[0], filters[1], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            #self.conv3 = UnetConv(filters[1], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            self.center = UnetConv(filters[1], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            # upsampling
            self.up_concat3 = UnetUp(filters[3], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            self.up_concat2 = UnetUp(filters[2], filters[1], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
            self.up_concat1 = UnetUp(filters[1], filters[0], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])

            # final conv (without any concat)
            self.final = SPTBack(filters[0], 7)
            if on_gpu:
                self.conv1.cuda()
                self.conv2.cuda()
                self.conv3.cuda()
                self.center.cuda()
                self.up_concat3.cuda()
                self.up_concat2.cuda()
                self.up_concat1.cuda()
                self.final.cuda()
            self.apply(weights_init)

        def forward(self, inputs: torch.Tensor):
            maxpool = nn.MaxPool2d(kernel_size=2)
            x_s = torch.chunk(inputs, 8, 2)
            along_x = []
            for i in x_s:
                chunks = torch.chunk(i, 8, 3)
                along_x.append(chunks)
            merge_x = []
            for chunks in along_x:
                merge_y = []
                for chunk in chunks:
                    conv1, theta = self.conv1(chunk)  # 16*64*64
                    maxpool1 = maxpool(conv1)  # 16*32*32

                    conv2 = self.conv2(maxpool1)  # 32*32*32
                    maxpool2 = maxpool(conv2)  # 32*16*16

                    center = self.center(maxpool2)

                   # up3 = self.up_concat3(center, conv2)  # 64*16*16
                    up2 = self.up_concat2(center, conv2)  # 32*32*32
                    up1 = self.up_concat1(up2, conv1)  # 16*64*64

                    final = self.final(up1, theta)
                    finalize = nn.functional.softmax(final, dim=1)
                    merge_y.append(finalize)
                merge_x.append(torch.cat(merge_y, 3))
            return torch.cat(merge_x, 2)



#### ==== Context Unet - just testing ==== ####
class ContextUnet(UnetSuper):
    def __init__(self, len_test_set, hparams, input_channels, is_deconv=True,
                 is_batchnorm=True, on_gpu=False, **kwargs):
        super().__init__(len_test_set=len_test_set, hparams=hparams, **kwargs)
        self.in_channels = input_channels
        self.is_deconv = is_deconv
        self.is_batchnorm = is_batchnorm
        self.input = input_channels
        filters = [32, 64, 128, 256]
        self.conv1 = UnetConv(self.in_channels, filters[0], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.context1 = Context(filters[0], filters[1], gpus=on_gpu)
        self.ttt1 = UnetConv(filters[1], filters[1], True, stride=2, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.context2 = Context(filters[1], filters[2], gpus=on_gpu)
        self.ttt2 = UnetConv(filters[2], filters[2], True, stride=2, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.context3 = Context(filters[2], filters[3], gpus=on_gpu)
        self.ttt3 = UnetConv(filters[3], filters[3], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.center = Context(filters[3], filters[3], gpus=on_gpu)
        self.up1 = UnetUp(filters[3], filters[2], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.local1 = Localization(filters[2], filters[2])
        self.up2 = UnetUp(filters[2], filters[1],  True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.local2 = Localization(filters[1], filters[1])
        self.up3 = UnetUp(filters[1], filters[0], True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])
        self.local3 = Localization(filters[0], filters[0])
        self.up4 = UnetUp(filters[0], 7,  True, gpus=on_gpu, dropout_val=kwargs["dropout_val"])




    def forward(self, x):
        maxpool = nn.MaxPool2d(kernel_size=2)
        con = self.conv1(x)
        son = self.context1(con)
        x = con + son
        return x