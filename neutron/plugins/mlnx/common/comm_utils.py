# Copyright 2013 Mellanox Technologies, Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import time

from oslo.config import cfg

from neutron.openstack.common import log as logging
from neutron.plugins.mlnx.common import config  # noqa

LOG = logging.getLogger(__name__)


class RetryDecorator(object):
    """Retry decorator reruns a method 'retries' times if an exception occurs.

    Decorator for retrying a method if exceptionToCheck exception occurs
    If method raises exception, retries 'retries' times with increasing
    back off period between calls with 'interval' multiplier

    :param exceptionToCheck: the exception to check
    :param interval: initial delay between retries in seconds
    :param retries: number of times to try before giving up
    :raises: exceptionToCheck
    """
    sleep_fn = time.sleep

    def __init__(self, exception_to_check,
                 interval=cfg.CONF.ESWITCH.request_timeout / 1000,
                 retries=cfg.CONF.ESWITCH.retries,
                 backoff_rate=cfg.CONF.ESWITCH.backoff_rate):
        self.exc = exception_to_check
        self.interval = interval
        self.retries = retries
        self.backoff_rate = backoff_rate

    def __call__(self, original_func):
        @functools.wraps(original_func)
        def decorated(*args, **kwargs):
            sleep_interval = self.interval
            num_of_iter = self.retries
            while num_of_iter > 0:
                try:
                    return original_func(*args, **kwargs)
                except self.exc:
                    LOG.debug(_("Request timeout - call again after "
                              "%s seconds"), sleep_interval)
                    RetryDecorator.sleep_fn(sleep_interval)
                    num_of_iter -= 1
                    sleep_interval *= self.backoff_rate

            return original_func(*args, **kwargs)
        return decorated
