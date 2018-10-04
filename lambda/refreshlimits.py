import json
import boto3

def lambda_handler(event, context):
    
    # EBS Check Ids
    #   'fH7LL0l7J9', 'dH7RR0l6J9', 'cG7HH0l7J9', 'tV7YY0l7J9', 'gI7MM0l7J9'
    # EC2 Check Ids    
    #   'aW9HH0l8J6', '0Xc6LMYG8P', 'iH7PP0l7J9' 

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