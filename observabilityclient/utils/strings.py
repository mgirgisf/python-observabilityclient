#   Copyright 2022 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#


STR_MASK = '*' * 8
COLORS = {'nocolor': "\033[0m",
          'red': "\033[0;31m",
          'green': "\033[32m",
          'blue': "\033[34m",
          'yellow': "\033[33m"}


def color_text(text, color):
    """Returns given text string with appropriate color tag. Allowed value
    for color parameter is 'red', 'blue', 'green' and 'yellow'.
    """
    return '%s%s%s' % (COLORS[color], text, COLORS['nocolor'])


def mask_string(unmasked, mask_list=None):
    """Replaces words from mask_list with MASK in unmasked string."""
    mask_list = mask_list or []

    masked = unmasked
    for word in mask_list:
        if not word:
            continue
        masked = masked.replace(word, STR_MASK)
    return masked
