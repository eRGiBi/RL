import matplotlib.pyplot as plt
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import HParam, TensorBoardOutputFormat
from stable_baselines3.common.monitor import load_results
from stable_baselines3.common.results_plotter import ts2xy
import wandb
from torch.utils.tensorboard import SummaryWriter


class FoundTargetsCallback(BaseCallback):
    """
    Callback for plotting the number of found targets during training.

    """
    def __init__(self, log_dir, verbose=1):
        super(FoundTargetsCallback, self).__init__(verbose)
        self.log_dir = log_dir
        self.episode_rewards = []

    def _on_step(self) -> bool:
        return True

    def _on_episode_end(self) -> None:
        print(self.model.ep_info_buffer)
        if self.model.ep_info_buffer:
            episode_info = self.model.ep_info_buffer[0]
            episode_rewards = episode_info.get('found_targets', None)
            print(episode_rewards)

            # Log episode rewards to TensorBoard
            if episode_rewards is not None:
                self.episode_rewards.append(episode_rewards[-1])
                self.logger.record('train/found_targets', episode_rewards[-1])
                wandb.log({'found_targets': episode_rewards[-1]})
                print("Found targets: ", episode_rewards[-1])


class HParamCallback(BaseCallback):
    """
    Saves the hyperparameters and metrics at the start of the training, and logs them to TensorBoard.
    """
    def _on_training_start(self) -> None:
        self.hparams = self.model.get_parameters()

        # Create a TensorBoard writer
        log_dir = self.model.tensorboard_log
        self.writer = SummaryWriter(log_dir)

        # Log hyperparameters
        for key, value in self.hparams.items():
            self.writer.add_text("hyperparameters", f"{key}: {value}")

    def _on_step(self) -> bool:
        return True

    def _on_training_end(self) -> None:
        """
        This method is called when the training ends.
        It closes the TensorBoard writer.
        """
        if self.writer is not None:
            self.writer.close()


class SummaryWriterCallback(BaseCallback):

    def _on_training_start(self):
        self._log_freq = 1000  # log every 1000 calls

        output_formats = self.logger.output_formats
        # Save reference to tensorboard formatter object
        # note: the failure case (not formatter found) is not handled here, should be done with try/except.
        self.tb_formatter = next(formatter for formatter in output_formats if isinstance(formatter, TensorBoardOutputFormat))

    def _on_step(self) -> bool:
        if self.n_calls % self._log_freq == 0:
            # You can have access to info from the env using self.locals.
            # for instance, when using one env (index 0 of locals["infos"]):
            # lap_count = self.locals["infos"][0]["lap_count"]
            # self.tb_formatter.writer.add_scalar("train/lap_count", lap_count, self.num_timesteps)

            self.tb_formatter.writer.add_text("direct_access", "this is a value", self.num_timesteps)
            self.tb_formatter.writer.flush()

        return True
