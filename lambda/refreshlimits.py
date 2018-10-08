import json
import boto3

def lambda_handler(event, context):

    checkIds = os.environ['SERVICE_CHECKS']

    support = boto3.client(service_name='support')

    try:
        for checkId in checkIds.split(','):
            support.refresh_trusted_advisor_check(checkId=checkId)
        
        return {
            'type': 'limits',
            'checkIds': checkIds
        }
  
    except Exception as e:
        print(e)
        message = 'Error refreshing Trusted Advisor Checks'
        print(message)
        raise Exception(message) 