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

"""Tanh bijector."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf  # pylint: disable=g-explicit-tensorflow-version-import
from tensorflow_probability.python.bijectors import bijector


__all__ = [
    "Tanh",
]


class Tanh(bijector.Bijector):
  """Bijector that computes `Y = tanh(X)`, therefore `Y in (-1, 1)`.

  This can be achieved by an affine transform of the Sigmoid bijector, i.e.,
  it is equivalent to
  ```
  tfb.Chain([tfb.Affine(shift=-1, scale=2.),
             tfb.Sigmoid(),
             tfb.Affine(scale=2.)])
  ```

  However, using the `Tanh` bijector directly is slightly faster and more
  numerically stable.
  """

  def __init__(self, validate_args=False, name="tanh"):
    parameters = dict(locals())
    super(Tanh, self).__init__(
        forward_min_event_ndims=0,
        validate_args=validate_args,
        parameters=parameters,
        name=name,
    )

  def _forward(self, x):
    return tf.nn.tanh(x)

  def _inverse(self, y):
    # 0.99999997 is the maximum value such that atanh(x) is valid for both
    # tf.float32 and tf.float64
    y = tf.where(
        tf.less_equal(tf.abs(y), 1.0),
        tf.clip_by_value(y, -0.99999997, 0.99999997),
        y,
    )
    return tf.atanh(y)

  def _forward_log_det_jacobian(self, x):
    #  This formula is mathematically equivalent to
    #  `tf.log1p(-tf.square(tf.tanh(x)))`, however this code is more numerically
    #  stable.

    #  Derivation:
    #    log(1 - tanh(x)^2)
    #    = log(sech(x)^2)
    #    = 2 * log(sech(x))
    #    = 2 * log(2e^-x / (e^-2x + 1))
    #    = 2 * (log(2) - x - log(e^-2x + 1))
    #    = 2 * (log(2) - x - softplus(-2x))
    return 2.0 * (
        tf.math.log(tf.constant(2.0, dtype=x.dtype))
        - x
        - tf.nn.softplus(-2.0 * x)
    )
