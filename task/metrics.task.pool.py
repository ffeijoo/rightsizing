import boto3
import codecs
import datetime as dt
import json
import multiprocessing
import os
import pandas as pd
import re
import sys
import time
from argparse import ArgumentParser
from functools import partial

def total_metrics(region, accountId, statistics, period, startTime, endTime):
    
    #boto3.setup_default_session(profile_name='')
    ec2 = boto3.resource('ec2', region_name = region)
    
    now = int(time.time() * 1000)
    
    instances = []

    try:          
        rs = ec2.meta.client.describe_instances()
    except Exception as e:
        print(e)
    
    if 'Reservations' in rs:
        for reservation in rs['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    instance['OwnerAccountId'] = accountId
                    instances.append(instance)

    pool = multiprocessing.Pool(multiprocessing.cpu_count() - 1)
    func = partial(instance_metrics, accountId, statistics, period, now, startTime, endTime)
    response = pool.map(func, instances)
    pool.close()
    pool.join()

    return response

def instance_metrics(accountId, statistics, period, now, startTime, endTime, instance):

    metric_units = { 
        'CPUUtilization': 'Percent',
        'NetworkIn': 'Bytes', 'NetworkOut': 'Bytes',
        'DiskReadOps': 'Count', 'DiskWriteOps': 'Count',
        'CPUCreditBalance': 'Count', 'CPUSurplusCreditBalance': 'Count' }

    df_output = pd.DataFrame([])

    for key in metric_units.keys():
        args = {
            'dimensions': [{'Name': 'InstanceId', 'Value': instance['InstanceId']}],
            'startTime': now - startTime,
            'endTime': now - endTime,
            'period': period,
            'statistics': [statistics],
            'metricName': key,
            'namespace': 'AWS/EC2',
            'unit': metric_units[key]
        }

        numRetries = 0
        gettingMetrics = True
        while gettingMetrics:
            try:
                session = boto3.session.Session(region_name=instance['Placement']['AvailabilityZone'][:-1])
                cloudwatch = session.resource('cloudwatch')
                result = cloudwatch.meta.client.get_metric_statistics(
                    Dimensions=args['dimensions'],
                    StartTime=dt.datetime.fromtimestamp(args['startTime']/1e3).strftime('%Y-%m-%d %H:%M:%S'),
                    EndTime=dt.datetime.fromtimestamp(args['endTime']/1e3).strftime('%Y-%m-%d %H:%M:%S'),
                    Period=args['period'],
                    Statistics=args['statistics'],
                    MetricName=args['metricName'],
                    Namespace=args['namespace'],
                    Unit=args['unit'])
                gettingMetrics = False
            except Exception as e:
                print(e)
                numRetries += 1
                if numRetries > 3:
                    gettingMetrics = False
                    raise
                    time.sleep(1)
        
            if len(result['Datapoints']) > 0:
                df = pd.DataFrame(result['Datapoints'])
                if 'Unit' in df.columns:
                    df.drop('Unit', axis=1, inplace=True)
                df.columns = [key, 'timestamp']
                
                if df_output.empty:
                    tagString = ''
                    ebsString = ''
                    if instance.tags:
                        for tag in instance.tags:
                            tagString += re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Key'].replace(',', ' ')) + ':' + re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Value'].replace(',', ' ')) + ' | '
                        tagString = tagString[:-3]
                    if instance.block_device_mappings:
                        for ebs in instance.block_device_mappings:
                            ebsString += ebs['Ebs']['VolumeId'] + ' | '
                        ebsString = ebsString[:-3]       
                    
                    df['humanReadableTimestamp'] = df['timestamp']
                    df['accountId'] = self.accountId
                    df['az'] = instance.placement['AvailabilityZone']
                    df['instanceId'] = instance.id
                    df['instanceType'] = instance.instance_type
                    df['instanceTags'] = tagString
                    df['ebsBacked'] = True if instance.root_device_type == 'ebs' else 'false'
                    df['volumeIds'] = ebsString
                    df['instanceLaunchTime'] = instance.launch_time
                    df['humanReadableInstanceLaunchTime'] = instance.launch_time
                    df_output = df_output.append(df)
                else:
                    df_output = pd.merge(df_output, df, on='timestamp')
        
        df_output.fillna(0)
    
    return df_output

def main():

    parser = ArgumentParser()
    parser.add_argument('--region')
    parser.add_argument('--account')
    parser.add_argument('--statistics')
    parser.add_argument('--period',)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--bucket')

    args = parser.parse_args()
    
    rs = total_metrics(
        args.region,
        args.account,
        args.statistics,
        int(args.period) * 60,
        int(args.start) * 60 * 60 * 1000,
        int(args.end) * 60 * 60 * 1000
    )

    now = dt.datetime.now()
    start = now - dt.timedelta(hours=int(args.start))
    end = now - dt.timedelta(hours=int(args.end))

    filename = args.region + '-' + format(start, '[%Y-%m-%d]') + '-' + format(end, '[%Y-%m-%d]')
    
    rs = rs.astype('str')

    parquet = filename + '.parquet'
    rs.to_parquet(parquet, compression='gzip')

    #csv = filename + '.csv'
    #rs.to_csv(path_or_buf=csv, index=False, quoting=1)

    s3 = boto3.resource('s3', region_name = args.region)
    s3.meta.client.upload_file(parquet, args.bucket, 'metrics/' + args.statistics + '/' + format(now, '%Y/%m/%d') + '/' + parquet)

    sys.exit(0)

if __name__ == "__main__":
    main()