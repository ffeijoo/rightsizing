select 
  (min(interval.sum.bits_per_second)/1000000000) as min,
  (max(interval.sum.bits_per_second)/1000000000) as max,
  (avg(interval.sum.bits_per_second)/1000000000) as avg,
  (approx_percentile(interval.sum.bits_per_second, 0.95)/1000000000) as p95,
  region, 
  instancetype 
from network cross join unnest(intervals) with ordinality as t(interval, counter)
-- WHERE cardinality(intervals) = 60
group by region,
         instancetype 
order by region,
         instancetype;