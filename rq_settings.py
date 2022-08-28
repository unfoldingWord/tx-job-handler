# TX RQ Settings

from os import getenv

# NOTE: These variable names are defined by the rq package

# Read the redis URL from an environment variable
REDIS_URL = getenv('REDIS_URL', 'redis://127.0.0.1:6379')
# You can also specify the Redis DB to use
# REDIS_HOST = 'redis.example.com'
# REDIS_PORT = 6380
# REDIS_DB = 3
# REDIS_PASSWORD = 'very secret'

# Queues to listen on
#QUEUES = ['high', 'normal', 'low'] # NOTE: The first queue in the list is processed first
queue_name = getenv('QUEUE_NAME', 'tx_job_handler') # Becomes the queue name — MUST match tx_enqueue_main.py in tx-enqueue-job
prefix = getenv('QUEUE_PREFIX', '') # Gets (optional) QUEUE_PREFIX environment variable—set to 'dev-' for development
suffix = getenv('QUEUE_SUFFIX', '') # Used to switch to a different queue, e.g., '_1'
webhook_queue_name = prefix + queue_name + suffix
QUEUES = [webhook_queue_name]

# If you're using Sentry to collect your runtime exceptions, you can use this
# to configure RQ for it in a single step
# The 'sync+' prefix is required for raven: https://github.com/nvie/rq/issues/350#issuecomment-43592410
#SENTRY_DSN = 'sync+http://public:secret@example.com/1'

# Our stuff
debug_mode_flag = getenv('DEBUG_MODE', 'True').lower() not in ['false', 'f', '', 0]
