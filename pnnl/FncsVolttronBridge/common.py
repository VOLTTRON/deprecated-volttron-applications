from volttron.platform.messaging import topics
from volttron.platform.messaging import utils

FNCS_BASE_TOPIC = 'fncs'
FNCS_INPUT_TOPIC = 'input'
FNCS_OUTPUT_TOPIC = 'output'

_FNCS_PATH = utils.Topic('{base}//{direction}//{path}')
FNCS_PATH = utils.Topic(_FNCS_PATH.replace('{base}', FNCS_BASE_TOPIC))
FNCS_INPUT_PATH = utils.Topic(FNCS_PATH.replace('{direction}', FNCS_INPUT_TOPIC))
FNCS_OUTPUT_PATH = utils.Topic(FNCS_PATH.replace('{direction}', FNCS_OUTPUT_TOPIC))

_FNCS_DEVICES_PATH = utils.Topic(FNCS_PATH.replace('{path}','{devices}//{campus}//{building}//{unit}//{path!S}//{point}'))
FNCS_DEVICES_PATH = utils.Topic(_FNCS_DEVICES_PATH.replace('{devices}', topics.DRIVER_TOPIC_BASE))
FNCS_DEVICES = FNCS_PATH(direction=FNCS_OUTPUT_TOPIC, path = topics.DRIVER_TOPIC_BASE)
FNCS_DEVICES_INPUT_PATH = utils.Topic(FNCS_DEVICES_PATH.replace('{direction}', FNCS_INPUT_TOPIC))
FNCS_DEVICES_OUTPUT_PATH = utils.Topic(FNCS_DEVICES_PATH.replace('{direction}', FNCS_OUTPUT_TOPIC))