"""Evidence contexts and fail-closed per-fact decisions."""
def seconds(stamp):
 h,m,s=map(int,stamp.split(':'));return h*3600+m*60+s
def expand(turns,selected,radius=3,time_radius=15):
 keys=list(turns);positions={key:i for i,key in enumerate(keys)};indices=set()
 for tid in selected:
  if tid not in positions:raise ValueError('Unknown evidence ID: '+tid)
  i=positions[tid];center=seconds(turns[tid]['time'])
  indices.update(range(max(0,i-radius),min(len(keys),i+radius+1)))
  indices.update(j for j,key in enumerate(keys) if abs(seconds(turns[key]['time'])-center)<=time_radius)
 return [turns[keys[i]] for i in sorted(indices)]
def accepted(check,source_ids):
 return (check.get('verdict')=='supported' and check.get('all_parts_supported') is True
  and check.get('final_status_confirmed') is True and bool(check.get('supporting_ids'))
  and not check.get('opposing_ids') and bool(check.get('reason','').strip())
  and all(t in source_ids for t in check.get('supporting_ids',[])))
