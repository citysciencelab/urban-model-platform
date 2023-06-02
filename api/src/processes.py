import logging
import yaml
import traceback
import aiohttp

PROVIDERS = yaml.safe_load(open('./configs/providers.yml'))

async def all_processes():
  processes = {}
  async with aiohttp.ClientSession() as session:
    for prefix in PROVIDERS:
      try:
        p = PROVIDERS[prefix]

        response = await session.get(
          f"{p['url']}/processes",
          auth=aiohttp.BasicAuth(p['user'], p['password']),
          headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        )
        async with response:
          assert response.status == 200, f"Response status {response.status}, {response.reason}"
          results = await response.json()

          if "processes" in results:
            processes[prefix] = results["processes"]
      except Exception as e:
        logging.error(f"Cannot access {prefix} provider! {e}")
        traceback.print_exc()
        processes[prefix] = []

  return _processes_list(processes)

def _processes_list(results):
  processes = []
  for prefix in PROVIDERS:
    for process in results[prefix]:
      if "exclude" in PROVIDERS[prefix] and process["id"] in PROVIDERS[prefix]["exclude"]:
        continue

      process["id"] = f"{prefix}:{process['id']}"
      processes.append(process)

  return { "processes": processes }
