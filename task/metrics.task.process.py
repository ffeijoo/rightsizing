import boto3
import codecs
import datetime as dt
import json
import os
import pandas as pd
import re
import sys
import time
from multiprocessing import Process, Pipe
from argparse import ArgumentParser

class MetricsParallel:
    def __init__(self, region, accountId, statistics, period, startTime, endTime):
        #boto3.setup_default_session(profile_name='')
        self.ec2 = boto3.resource('ec2', region_name = region)
        self.accountId = accountId
        self.statistics = statistics
        self.period = period
        self.startTime = startTime
        self.endTime = endTime

    def total_metrics(self):

        metric_units = { 
            'CPUUtilization': 'Percent',
            'NetworkIn': 'Bytes', 'NetworkOut': 'Bytes',
            'DiskReadOps': 'Count', 'DiskWriteOps': 'Count',
            'CPUCreditBalance': 'Count', 'CPUSurplusCreditBalance': 'Count' }

        instances = []

        try:          
            instances = self.ec2.instances.filter(
                Filters=[{'Name': 'instance-state-name','Values': ['running']}])
        
        except Exception as e:
            print(e)
        
        processes = []
        parent_connections = []
  
        now = int(time.time() * 1000)
        
        for instance in instances:            

            parent_conn, child_conn = Pipe()
            parent_connections.append(parent_conn)

            process = Process(target=self.instance_metrics, args=(now, metric_units, instance, child_conn))
            processes.append(process)

        for process in processes:
            process.start()

        for process in processes:
            process.join()

        metrics = pd.DataFrame([])
        for parent_connection in parent_connections:
            metrics = metrics.append(parent_connection.recv()[0], sort=False)

        return metrics

    def instance_metrics(self, now, metric_units, instance, conn):
        
        df_output = pd.DataFrame([])

        for key in metric_units.keys():
            args = {
                'dimensions': [{'Name': 'InstanceId', 'Value': instance.id}],
                'startTime': now - self.startTime,
                'endTime': now - self.endTime,
                'period': self.period,
                'statistics': [self.statistics],
                'metricName': key,
                'namespace': 'AWS/EC2',
                'unit': metric_units[key]
            }

            numRetries = 0
            gettingMetrics = True
            while gettingMetrics:
                try:
                    session = boto3.session.Session(region_name=instance.placement['AvailabilityZone'][:-1])
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
        
        conn.send([df_output])
        conn.close()

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
    
    metrics = MetricsParallel(
        args.region,
        args.account,
        args.statistics,
        int(args.period) * 60,
        int(args.start) * 60 * 60 * 1000,
        int(args.end) * 60 * 60 * 1000
    )

    rs = metrics.total_metrics()

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