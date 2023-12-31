# coding=utf-8
# Copyright 2020 The TF-Agents Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Network Outputting Expected Value and Variance of Rewards."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
from typing import Any, Callable, Optional, Sequence, Text

import gin
import tensorflow as tf  # pylint: disable=g-explicit-tensorflow-version-import
from tf_agents.networks import encoding_network
from tf_agents.networks import network
from tf_agents.networks import q_network
from tf_agents.typing import types


class QBanditNetworkResult(
    collections.namedtuple(
        'QBanditNetworkResult', ('q_value_logits', 'log_variance')
    )
):
  pass


@gin.configurable
class HeteroscedasticQNetwork(network.Network):
  """Network Outputting Expected Value and Variance of Rewards."""

  def __init__(
      self,
      input_tensor_spec: types.NestedTensorSpec,
      action_spec: types.NestedTensorSpec,
      preprocessing_layers: Optional[Callable[..., types.Tensor]] = None,
      preprocessing_combiner: Optional[Callable[..., types.Tensor]] = None,
      conv_layer_params: Optional[Sequence[Any]] = None,
      fc_layer_params: Sequence[int] = (75, 40),
      dropout_layer_params: Optional[Sequence[float]] = None,
      activation_fn: Callable[
          [types.Tensor], types.Tensor
      ] = tf.keras.activations.relu,
      kernel_initializer: Optional[tf.keras.initializers.Initializer] = None,
      batch_squash: bool = True,
      min_variance: float = 0.1,
      max_variance: float = 10000.0,
      dtype: tf.DType = tf.float32,
      name: Text = 'HeteroscedasticQNetwork',
  ):
    """Creates an instance of `HeteroscedasticQNetwork`.

    Args:
      input_tensor_spec: A nest of `tensor_spec.TensorSpec` representing the
        input observations.
      action_spec: A nest of `tensor_spec.BoundedTensorSpec` representing the
        actions.
      preprocessing_layers: (Optional.) A nest of `tf.keras.layers.Layer`
        representing preprocessing for the different observations. All of these
        layers must not be already built. For more details see the documentation
        of `networks.EncodingNetwork`.
      preprocessing_combiner: (Optional.) A keras layer that takes a flat list
        of tensors and combines them. Good options include `tf.keras.layers.Add`
        and `tf.keras.layers.Concatenate(axis=-1)`. This layer must not be
        already built. For more details see the documentation of
        `networks.EncodingNetwork`.
      conv_layer_params: Optional list of convolution layers parameters, where
        each item is a length-three tuple indicating (filters, kernel_size,
        stride).
      fc_layer_params: Optional list of fully_connected parameters, where each
        item is the number of units in the layer.
      dropout_layer_params: Optional list of dropout layer parameters, where
        each item is the fraction of input units to drop. The dropout layers are
        interleaved with the fully connected layers; there is a dropout layer
        after each fully connected layer, except if the entry in the list is
        None. This list must have the same length of fc_layer_params, or be
        None.
      activation_fn: Activation function, e.g. tf.keras.activations.relu.
      kernel_initializer: Initializer to use for the kernels of the conv and
        dense layers. If none is provided a default variance_scaling_initializer
      batch_squash: If True the outer_ranks of the observation are squashed into
        the batch dimension. This allow encoding networks to be used with
        observations with shape [BxTx...].
      min_variance: Float. The minimum allowed predicted variance. Predicted
        variances less than this value will be clipped to this value.
      max_variance: Float. The maximum allowed predicted variance. Predicted
        variances greater than this value will be clipped to this value.
      dtype: The dtype to use by the convolution and fully connected layers.
      name: A string representing the name of the network.

    Raises:
      ValueError: If `input_tensor_spec` contains more than one observation. Or
        if `action_spec` contains more than one action.
    """
    q_network.validate_specs(action_spec, input_tensor_spec)
    action_spec = tf.nest.flatten(action_spec)[0]
    num_actions = action_spec.maximum - action_spec.minimum + 1
    encoder_input_tensor_spec = input_tensor_spec

    encoder = encoding_network.EncodingNetwork(
        encoder_input_tensor_spec,
        preprocessing_layers=preprocessing_layers,
        preprocessing_combiner=preprocessing_combiner,
        conv_layer_params=conv_layer_params,
        fc_layer_params=fc_layer_params,
        dropout_layer_params=dropout_layer_params,
        activation_fn=activation_fn,
        kernel_initializer=kernel_initializer,
        batch_squash=batch_squash,
        dtype=dtype,
    )

    q_value_layer = tf.keras.layers.Dense(
        num_actions,
        activation=None,
        kernel_initializer=tf.random_uniform_initializer(
            minval=-0.03, maxval=0.03
        ),
        bias_initializer=tf.constant_initializer(-0.2),
    )

    super(HeteroscedasticQNetwork, self).__init__(
        input_tensor_spec=input_tensor_spec, state_spec=(), name=name
    )

    self._encoder = encoder
    self._q_value_layer = q_value_layer

    self._log_variance_layer = tf.keras.layers.Dense(
        num_actions,
        activation=None,
        kernel_initializer=tf.random_uniform_initializer(
            minval=-0.03, maxval=0.03
        ),
        dtype=dtype,
    )

    self._min_variance = min_variance
    self._max_variance = max_variance

  def call(self, observation, step_type=None, network_state=()):
    """Runs the given observation through the network.

    Args:
      observation: The observation to provide to the network.
      step_type: The step type for the given observation. See `StepType` in
        time_step.py.
      network_state: A state tuple to pass to the network, mainly used by RNNs.

    Returns:
      An instance of `QBanditNetworkResult`.
    """
    state, network_state = self._encoder(
        observation, step_type=step_type, network_state=network_state
    )

    log_variance = tf.clip_by_value(
        self._log_variance_layer(state),
        tf.math.log(self._min_variance),
        tf.math.log(self._max_variance),
    )

    q_value_logits = self._q_value_layer(state)

    result = QBanditNetworkResult(q_value_logits, log_variance)

    return (result, network_state)
