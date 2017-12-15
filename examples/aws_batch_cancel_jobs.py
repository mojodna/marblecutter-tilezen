import argparse
import boto3
import time
from itertools import islice


def iter_jobs(client, queue_arn, status):
    next_token = ''
    while True:
        result = client.list_jobs(
            jobQueue=queue_arn, jobStatus=status, nextToken=next_token)

        job_summary_list = result.get('jobSummaryList')
        for job in job_summary_list:
            yield job

        next_token = result.get('nextToken')

        if next_token is None:
            break


def grouper(n, iterable):
    iterable = iter(iterable)
    return iter(lambda: list(islice(iterable, n)), [])


def cancel_jobs(queue_arn, state):
    client = boto3.client('batch')

    for summary_group in grouper(50, iter_jobs(client, queue_arn, state)):
        job_ids = [summary['jobId'] for summary in filter(None, summary_group)]

        for job_id in job_ids:
            client.cancel_job(
                jobId=job_id,
                reason="Canceled with cancel_batch_jobs.py",
            )
            print("Canceled job {}".format(job_id))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'queue',
        help='The AWS Batch queue ARN to look for jobs on'
    )
    parser.add_argument(
        'state',
        help='Only cancel jobs that are presently in this job state',
        choices=['SUBMITTED', 'PENDING', 'RUNNABLE']
    )

    args = parser.parse_args()

    cancel_jobs(args.queue, args.state)
