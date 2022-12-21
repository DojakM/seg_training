import os
from argparse import ArgumentParser
import mlflow
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import TensorBoardLogger
from rich import print

from mlf_core.mlf_core import MLFCore
from seg_training_main.model.unet_instance import Unet
from data_loading.conic_data import ConicDataModule

if __name__ == "__main__":
    parser = ArgumentParser(description='PyTorch Autolog PHDFM Example')
    parser.add_argument(
        '--general-seed',
        type=int,
        default=0,
        help='General random seed',
    )
    parser.add_argument(
        '--pytorch-seed',
        type=int,
        default=0,
        help='Random seed of all Pytorch functions',
    )
    parser.add_argument(
        '--log-interval',
        type=int,
        default=100,
        help='log interval of stdout',
    )
    parser = pl.Trainer.add_argparse_args(parent_parser=parser)
    parser = Unet.add_model_specific_args(parent_parser=parser)
    # log conda env and system information
    # MLFCore.log_sys_intel_conda_env()
    # parse cli arguments
    args = parser.parse_args()
    dict_args = vars(args)
    # store seed
    # number of gpus to make linter bit less restrict in terms of naming
    general_seed = dict_args['general_seed']
    pytorch_seed = dict_args['pytorch_seed']
    num_of_gpus = 0

    MLFCore.set_general_random_seeds(general_seed)
    MLFCore.set_pytorch_random_seeds(pytorch_seed, num_of_gpus)

    if 'accelerator' in dict_args:
        if dict_args['accelerator'] == 'None':
            dict_args['accelerator'] = None
        elif dict_args['accelerator'] != 'dp':
            print(
                f'[bold red]{dict_args["accelerator"]}[bold blue] currently not supported. Switching to [bold green]ddp!')
            dict_args['accelerator'] = 'dp'

    dm = ConicDataModule(**dict_args)

    #MLFCore.log_input_data('seg_training_main/data/PHDFM')
    if 'class_weights' not in dict_args.keys():
        weights = dm.df_train.class_weights
        dict_args['class_weights'] = weights['weights'].tolist()



    dm.setup(stage='fit')
    # Supported batch size:24
    # Supported batch size:96
    model = Unet(7, hparams=parser.parse_args(), len_test_set=len(dm.df_test), input_channels=3,
                 min_filter=64, **dict_args)
    model.log_every_n_steps = dict_args['log_interval']

    # check, whether the run is inside a Docker container or not
    if 'MLF_CORE_DOCKER_RUN' in os.environ:
        checkpoint_callback = ModelCheckpoint(filename="seg_training_main/mlruns/0", save_top_k=0, verbose=True,
                                              monitor='train_avg_loss', mode='min')
        trainer = pl.Trainer.from_argparse_args(args, checkpoint_callback=checkpoint_callback, default_root_dir='/data',
                                                logger=TensorBoardLogger('/data'))
        tensorboard_output_path = f'data/default/version_{trainer.logger.version}'
    else:
        checkpoint_callback = ModelCheckpoint(filename=f'{os.getcwd()}/mlruns/best', save_top_k=1,
                                              verbose=True, monitor='val_avg_iou', mode='max')
        trainer = pl.Trainer.from_argparse_args(args, callbacks=[checkpoint_callback],
                                                default_root_dir=os.getcwd() + "/mlruns",
                                                logger=TensorBoardLogger('data'))
        tensorboard_output_path = f'data/default/version_{trainer.logger.version}'

    trainer.deterministic = True
    trainer.benchmark = False
    trainer.log_every_n_steps = dict_args['log_interval']
    trainer.fit(model, dm)
    trainer.test()
    print(f'\n[bold blue]For tensorboard log, call [bold green]tensorboard --logdir={tensorboard_output_path}')
    print(checkpoint_callback.best_model_score.item())
    with open('best.txt', 'w') as f:
        f.write(str(checkpoint_callback.best_model_score.item()))
