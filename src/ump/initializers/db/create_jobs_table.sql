CREATE DATABASE cut_dev;

\c cut_dev

CREATE TYPE status AS ENUM ('accepted', 'running', 'successful', 'failed', 'dismissed');

CREATE TABLE IF NOT EXISTS jobs (
  process_id       varchar(80),
  job_id           varchar(80) PRIMARY KEY,
  remote_job_id    varchar(80),
  provider_prefix  varchar(80),
  provider_url     varchar(80),
  status           status,
  message          text,
  created          timestamp,
  started          timestamp,
  finished         timestamp,
  updated          timestamp,
  progress         integer,
  parameters       json,
  results_metadata json
);
