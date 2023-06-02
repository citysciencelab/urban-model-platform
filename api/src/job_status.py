from enum import Enum

class JobStatus(Enum):
  """
  Enum for the job status options specified in the WPS 2.0 specification
  """
  accepted = 'accepted'
  running = 'running'
  successful = 'successful'
  failed = 'failed'
  dismissed = 'dismissed'
