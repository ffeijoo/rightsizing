import json
import boto3
import os

def lambda_handler(event, context):

    try:
        crawlerName = os.environ['CRAWLER_NAME']
        response = boto3.client(service_name='glue').start_crawler(
            Name=crawlerName,
        )
                
        return {
            'type': 'crawler',
            'crawlerName': crawlerName
        }
    except Exception as e:
        print(e)
        message = 'Error starting Crawler'
        print(message)
        raise Exception(message) 