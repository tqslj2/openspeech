# MIT License
#
# Copyright (c) 2021 Soohwan Kim and Sangchun Ha and Soyoung Cho
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import torch
from omegaconf import DictConfig
from collections import OrderedDict
from typing import Dict

from openspeech.decoders.lstm_decoder import LSTMDecoder
from openspeech.models import register_model, OpenspeechModel
from openspeech.models.lstm_lm.configurations import LSTMLanguageModelConfigs
from openspeech.vocabs.vocab import Vocabulary


@register_model('lstm_lm', dataclass=LSTMLanguageModelConfigs)
class LSTMLanguageModel(OpenspeechModel):
    def __init__(self, configs: DictConfig, vocab: Vocabulary, ) -> None:
        super(LSTMLanguageModel, self).__init__(configs, vocab)
        self.teacher_forcing_ratio = configs.model.teacher_forcing_ratio

    def build_model(self):
        self.lm = LSTMDecoder(
            num_classes=self.num_classes,
            max_length=self.configs.model.max_length,
            hidden_state_dim=self.configs.model.hidden_state_dim,
            pad_id=self.vocab.pad_id,
            sos_id=self.vocab.sos_id,
            eos_id=self.vocab.eos_id,
            dropout_p=self.configs.model.dropout_p,
            num_layers=self.configs.model.num_layers,
            rnn_type=self.configs.model.rnn_type,
        )

    def collect_outputs(
            self,
            stage: str,
            logits: torch.Tensor,
            targets: torch.Tensor,
    ) -> OrderedDict:
        loss = self.criterion(logits, targets[:, 1:])
        y_hats = logits.max(-1)[1]

        wer = self.wer_metric(targets, y_hats)
        cer = self.cer_metric(targets, y_hats)

        self.log_steps(stage, wer, cer, loss)

        progress_bar_dict = {
            f"{stage}_perplexity": loss,
            "wer": wer,
            "cer": cer,
        }

        return OrderedDict({
            "loss": loss,
            "progress_bar": progress_bar_dict,
            "log": progress_bar_dict,
        })

    def forward(self, inputs: torch.Tensor) -> Dict[str, torch.Tensor]:
        logits = self.lm(inputs, teacher_forcing_ratio=0.0)
        predictions = logits.max(-1)[1]
        return {
            "predictions": predictions,
            "logits": logits,
        }

    def training_step(self, batch: tuple, batch_idx: int) -> OrderedDict:
        r"""
        Forward propagate a `inputs` and `targets` pair for training.

        Inputs:
            train_batch (tuple): A train batch contains `inputs`
            batch_idx (int): The index of batch

        Returns:
            loss (torch.Tensor): loss for training
        """
        inputs, targets = batch
        logits = self.lm(inputs, teacher_forcing_ratio=self.teacher_forcing_ratio)
        return self.collect_outputs(
            stage='train',
            logits=logits,
            targets=targets,
        )

    def validation_step(self, batch: tuple, batch_idx: int) -> OrderedDict:
        r"""
        Forward propagate a `inputs` and `targets` pair for validation.

        Inputs:
            train_batch (tuple): A train batch contains `inputs`
            batch_idx (int): The index of batch

        Returns:
            loss (torch.Tensor): loss for training
        """
        inputs, targets = batch
        logits = self.lm(inputs, teacher_forcing_ratio=0.0)
        return self.collect_outputs(
            stage='valid',
            logits=logits,
            targets=targets,
        )

    def test_step(self, batch: tuple, batch_idx: int) -> OrderedDict:
        r"""
        Forward propagate a `inputs` and `targets` pair for test.

        Inputs:
            train_batch (tuple): A train batch contains `inputs`
            batch_idx (int): The index of batch

        Returns:
            loss (torch.Tensor): loss for training
        """
        inputs, targets = batch
        logits = self.lm(inputs, teacher_forcing_ratio=0.0)
        return self.collect_outputs(
            stage='test',
            logits=logits,
            targets=targets,
        )
