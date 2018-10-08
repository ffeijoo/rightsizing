import json
import boto3
import os

def lambda_handler(event, context):

    glue = boto3.client(service_name='glue')

    try:  
      job = glue.get_job(
        JobName=os.environ['JOB_NAME']
      )
    except Exception as e:
      print('Job not found, creating')
      create_job() 

    try:   
      response = glue.start_job_run(
        JobName=os.environ['JOB_NAME']
      )
      return {
        'type': 'job',
        'jobName': os.environ['JOB_NAME'],
        'runId': response['JobRunId'],
        'crawlerName': ''
      }
    except Exception as e:
      print(e)
      message = 'Error running Job'
      print(message)
      raise Exception(message)     

def create_job():

    glue = boto3.client(service_name='glue')

    try:
      
      source = {
        'DatabaseName': os.environ['JOB_DATABASE_NAME'],
        'TableName': os.environ['JOB_TABLE_NAME']
      }

      location = {
        'S3': [
          {
            'Name': 'path',
            'Value': os.environ['JOB_TARGET_PATH']
          },
          {
            'Name': 'classification',
            'Value': 'parquet'                
          }
        ]
      }

      script = glue.get_plan(
        Mapping=
          glue.get_mapping(
            Source=source,
            Location=location
          )['Mapping'],
        Source=source,
        Location=location,
        Language='PYTHON'
      )

      boto3.client(service_name='s3').put_object(
          Body=script['PythonScript'], 
          Bucket=os.environ['SCRIPT_BUCKET_NAME'], 
          Key=os.environ['SCRIPT_KEY_NAME']
      )

      scriptLocation = 's3://' + os.environ['SCRIPT_BUCKET_NAME'] + '/' + os.environ['SCRIPT_KEY_NAME']
      glue.create_job(
          Name=os.environ['JOB_NAME'],
          Role=os.environ['ROLE_ARN'],
          Command={
            'Name':'glueetl',
            'ScriptLocation': scriptLocation
          }
      )
    
    except Exception as e:
      print(e)
      message = 'Error creating Job'
      print(message)
      raise Exception(message) 