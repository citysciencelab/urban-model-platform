from src.db_handler import DBHandler
from src.job_status import JobStatus
from src.job import Job
import re

def get_jobs(args):
  page  = int(args["page"][0]) if "page" in args else 1
  limit = int(args["limit"][0]) if "limit" in args else None

  jobs = []
  query = """
    SELECT job_id FROM jobs
  """
  query_params = {}
  conditions = []

  if 'processID' in args and args['processID']:
    # this processID is actually the process_id_with_prefix!!!
    # we cannot change the name because it would not be OGC processes compliant anymore
    process_ids = []

    for process_id_with_prefix in args['processID']:
      match = re.search(r'(.*):(.*)', process_id_with_prefix)
      provider_prefix = match.group(1)
      process_ids.append(match.group(2))

    conditions.append("process_id IN %(process_id)s")
    query_params['process_id'] = tuple(process_ids)

    conditions.append("provider_prefix = %(provider_prefix)s")
    query_params['provider_prefix'] = provider_prefix

  if 'status' in args:
    query_params['status'] = tuple(args['status'])

  else:
    query_params['status'] = (
      JobStatus.running.value, JobStatus.successful.value,
      JobStatus.failed.value, JobStatus.dismissed.value
    )
  conditions.append("status IN %(status)s")

  db_handler = DBHandler()
  db_handler.set_sortable_columns(Job.SORTABLE_COLUMNS)

  with db_handler as db:
    job_ids = db.run_query(query,
      conditions   = conditions,
      query_params = query_params,
      order        = ['created'],
      limit        = limit,
      page         = page
    )

  for row in job_ids:
    job = Job(row['job_id'])
    jobs.append(job.display())

  count_jobs = count(conditions, query_params)
  links = next_links(page, limit, count_jobs)

  return { "jobs": jobs, "links": links, "total_count": count_jobs }

def next_links(page, limit, count_jobs):
  if not limit or count_jobs <= limit:
    return []

  links = []
  if count_jobs > (page - 1) * limit:
    links.append({
      "href": f"/api/jobs?page={page+1}&limit={limit}",
      "rel": "service",
      "type": "application/json",
      "hreflang": "en",
      "title": f"Next page of jobs."
    })

  if page > 1:
    links.append({
      "href": f"/api/jobs?page={page-1}&limit={limit}",
      "rel": "service",
      "type": "application/json",
      "hreflang": "en",
      "title": f"Previous page of jobs."
    })

  return links

def count(conditions, query_params):
  count_query = """
    SELECT count(*) FROM jobs
  """
  with DBHandler() as db:
    count_jobs = db.run_query(
      count_query,
      conditions=conditions,
      query_params=query_params
    )
  return count_jobs[0]['count']


