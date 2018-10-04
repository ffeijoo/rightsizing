import json
import boto3
import csv
import os
import io
import datetime as dt

def lambda_handler(event, context):

    checkIds = os.environ['SERVICE_CHECKS']

    support = boto3.client(service_name='support')

    out = io.StringIO()
    writer = csv.writer(out, delimiter=',', quoting=csv.QUOTE_MINIMAL)

    out.write(
        u"\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\",\"{5}\"\n".format(
            'region', 'serviceName', 'checkName', 'limit', 'usage', 'status'))

    try:
        for checkId in checkIds.split(','):
            
            response = support.describe_trusted_advisor_check_result(
                checkId=checkId,
                language='en'
            )
            
            flag_list = response['result']['flaggedResources']

            for flag_item in flag_list:
                  
                if flag_item['metadata'][0] == "-":
                    flag_item['metadata'][0] = "global"

                out.write(
                    u"\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\",\"{5}\"\n".format(
                        flag_item['metadata'][0],  # is the region name
                        flag_item['metadata'][1],  # is the service name
                        flag_item['metadata'][2],  # is the check name
                        flag_item['metadata'][3],  # is the resource limit
                        flag_item['metadata'][4],  # is the resource usage
                        flag_item['metadata'][5])) # is the flag status
        
        boto3.client(service_name='s3').put_object(
            Body=out.getvalue(), Bucket=os.environ['BUCKET_NAME'], Key='limits/tachecks.csv', Metatada={
                'created_date': str(dt.datetime.date.today())
            })
  
    except Exception as e:
        print(e)
        message = 'Error refreshing Trusted Advisor Checks'
        print(message)
        raise Exception(message) 