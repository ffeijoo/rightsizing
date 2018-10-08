import json
import boto3
import os

def lambda_handler(event, context):

    if event['type'] == 'task':
        clusterName = event['clusterName']
        taskArn = event['taskArn']
        try:
            response = boto3.client(service_name='ecs').describe_tasks(
                cluster=clusterName,
                tasks=[taskArn]
            )
            taskStatus = response['tasks'][0]['lastStatus']
            
            return taskStatus
        
        except Exception as e:
            print(e)
            message = 'Error getting Task status'
            print(message)
            raise Exception(message)
            
    elif event['type'] == 'crawler':
        crawlerName = event['crawlerName']
        try:
            response = boto3.client(service_name='glue').get_crawler(
                Name=crawlerName
            )
            crawlerState = response['Crawler']['State']
            
            if crawlerState == 'READY':
                return response['Crawler']['LastCrawl']['Status']
            else:
                return crawlerState
        
        except Exception as e:
            print(e)
            message = 'Error getting Crawler status'
            print(message)
            raise Exception(message)
    
    elif event['type'] == 'limits':
        checkIds = event['checkIds'].split(',')
        try:
            response = boto3.client(service_name='support').describe_trusted_advisor_check_refresh_statuses(
                checkIds=checkIds)

            ready = True
            for item in response['statuses']:
                status = item[status]
                ready = ready and ( status == 'success' or status == 'none')

                if status == 'abandoned':
                    return 'FAILED'

            return 'SUCCEEDED' if ready else 'PENDING'
        
        except Exception as e:
            print(e)
            message = 'Error getting Trusted Advisor Check Refresh status'
            print(message)
            raise Exception(message)

    elif event['type'] == 'job':
        runId = event['runId'].split(',')
        try:
            response = boto3.client(service_name='glue').get_job_run(
                JobName=event['jobName'],
                RunId=event['runId'])

            return response['JobRun']['JobRunState']
        
        except Exception as e:
            print(e)
            message = 'Error getting Job status'
            print(message)
            raise Exception(message)