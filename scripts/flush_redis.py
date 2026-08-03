import redis

r = redis.Redis(host='127.0.0.1', port=6379, db=0)

pending_before = r.llen('loot_raiders:mirror_queue:pending')
print('Pending count before:', pending_before)

r.delete('loot_raiders:mirror_queue:pending')

processing_keys = r.keys('loot_raiders:mirror_queue:processing:*')
for k in processing_keys:
    r.delete(k)

pending_after = r.llen('loot_raiders:mirror_queue:pending')
print('Pending count after:', pending_after)
print('Deleted processing keys count:', len(processing_keys))
