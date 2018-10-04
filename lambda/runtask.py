import json
import boto3
import os

def lambda_handler(event, context):
    clusterName = os.environ['CLUSTER_NAME']
    try:
        response = boto3.client(service_name='ecs').run_task(
            cluster=clusterName,
            taskDefinition=os.environ['TASK_DEFINITION_ARN'],
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': [
                        os.environ['SUBNET_ONE_ID'],
                        os.environ['SUBNET_TWO_ID']
                    ],
                    'assignPublicIp': 'ENABLED'
                }
            }
        )
        
        taskArn = response['tasks'][0]['taskArn']
        
        return {
            'type': 'task',
            'clusterName': clusterName,
            'taskArn': taskArn
        }
        
    except Exception as e:
        print(e)
        message = 'Error submitting Task'
        print(message)
        raise Exception(message) 