# Copyright 2022 MosaicML LLM Foundry authors
# SPDX-License-Identifier: Apache-2.0

import logging

from composer.core import Callback, State
from composer.loggers import Logger

from llmfoundry.utils.warnings import experimental_class

__all__ = [
    'GlobalLRScaling',
    'LayerFreezing',
]

log = logging.getLogger(__name__)


@experimental_class('GlobalLRScaling')
class GlobalLRScaling(Callback):
    """GlobalLRScaling.

    This callback can be applied upon resuming a model checkpoint. Upon
    fit_start it will multiply the base LR by `lr_scale` and set the WD to be.

    `wd_pct` * `lr`.

    Args:
        lr_scale (float): Multiplicative factor to scale LR by
        wd_pct (float): Percentage of LR to set weight decay to.
    """

    def __init__(self, lr_scale: float, wd_pct: float = 0.0):
        self.lr_scale = lr_scale
        self.wd_pct = wd_pct

    def fit_start(self, state: State, logger: Logger) -> None:
        del logger  # unused

        if hasattr(state, 'optimizer') and state.optimizers is None:
            raise Exception('No optimizers defined')
        for optimizer in state.optimizers:
            for group in optimizer.param_groups:
                group['lr'] *= self.lr_scale
                group['weight_decay'] = group['lr'] * self.wd_pct
                if 'initial_lr' in group:
                    group['initial_lr'] *= self.lr_scale
                log.info(
                    f"Set LR and WD to {group['lr']}, {group['weight_decay']}",
                )

        for scheduler in state.schedulers:
            scheduler.base_lrs = [
                self.lr_scale * lr for lr in scheduler.base_lrs
            ]


@experimental_class('LayerFreezing')
class LayerFreezing(Callback):
    """LayerFreezing.

    This callback can be applied upon resuming a model checkpoint. Upon
    fit_start it freeze the layers specified in `layer_names`. If using
    activation checkpointing, please set the
    `activation_checkpointing_reentrant` flag in `fsdp_config` to false.

    Args:
        layer_names (float): Names of layers to freeze.
    """

    def __init__(self, layer_names: list[str]):
        self.layer_names = set(layer_names)

    def fit_start(self, state: State, logger: Logger) -> None:
        del logger  # unused

        model_layers = {name for name, _ in state.model.named_parameters()}
        for layer in self.layer_names:
            if layer not in model_layers:
                raise Exception(
                    f'Attempted to freeze layer not found in model: {layer}\nAvailable layers: {model_layers}',
                )

        successful_freeze = False
        for name, p in state.model.named_parameters():
            if p.requires_grad and name in self.layer_names:
                p.requires_grad = False
                log.debug(f'Froze layer: {name}\nParam: {p}')
                successful_freeze = True

        if not successful_freeze:
            raise Exception(
                f"Tried to run LayerFreezing but didn't freeze any layers",
            )
