  select 
    a.az,
    a.instancetype,
    b.vcpu,
    b.memory,
    b.storage,
    b."network performance",
    b."processor architecture",
    b.priceperunit,
    a.instanceid,
    approx_percentile(a.p95cpu,     0.95) as p95cpu,
    approx_percentile(a.p95iops,    0.95) as p95iops,
    approx_percentile(a.p95network, 0.95) as p95network,
    a.instancetags from 
      (
          select instanceid, 
              instancetags, 
              instanceType, 
              az,
              approx_percentile(CPUUtilization, 0.95) as p95cpu,
              approx_percentile((diskreadops/60 + diskwriteops/60), 0.95) as p95iops,
              approx_percentile(((networkin/60/1024/1024)*8 + (networkout/60/1024/1024)*8), 0.95) as p95network
          from metrics 
          where accountid is not null
          group by instanceid, 
                  instancetags,
                  instanceType,
                  az
      ) a, 
        prices b 
  where a.instancetype = b."instance type"
  and substr(a.az, 1, length(a.az)-1) = case b.location
              when 'US East (Ohio)' then 'us-east-2'
              when 'US East (N. Virginia)' then 'us-east-1'
              when 'US West (N. California)' then 'us-west-1'
              when 'US West (Oregon)' then 'us-west-2'
              when 'Asia Pacific (Mumbai)' then 'ap-south-1'
              when 'Asia Pacific (Seoul)' then 'ap-northeast-2'
              when 'Asia Pacific (Osaka-Local)' then 'ap-northeast-3'
              when 'Asia Pacific (Singapore)' then 'ap-southeast-1'
              when 'Asia Pacific (Sydney)' then 'ap-southeast-2'
              when 'Asia Pacific (Tokyo)' then 'ap-northeast-1'
              when 'Canada (Central)' then 'ca-central-1'
              when 'China (Beijing)' then 'cn-north-1'
              when 'China (Ningxia)' then 'cn-northwest-1'
              when 'EU (Frankfurt)' then 'eu-central-1'
              when 'EU (Ireland)' then 'eu-west-1'
              when 'EU (London)' then 'eu-west-2'
              when 'EU (Paris)' then 'eu-west-3'
              when 'South America (Sao Paulo)' then 'sa-east-1'
            end
  and b.termtype = 'OnDemand'
  and b.servicecode = 'AmazonEC2'
  and b.tenancy = 'Shared'
  and b."operating system" = 'Linux' 
  and b."pre installed s/w" = 'NA'
  group by a.az,
          a.instancetype,
          b.vcpu,
          b.memory,
          b.storage,
          b."network performance",
          b."processor architecture",
          b.priceperunit,
          a.instanceid,
          a.instancetags