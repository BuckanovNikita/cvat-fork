import os, sys, time, requests

BASE = 'http://localhost:8181/api'
USER, PASSWORD = 'admin', 'verify-pass-123'
IMG_DIR = sys.argv[1]

s = requests.Session()
r = s.post(f'{BASE}/auth/login', json={'username': USER, 'password': PASSWORD}, timeout=30)
r.raise_for_status()
s.headers['Authorization'] = f"Token {r.json()['key']}"

def make_task(name, segment_size, images):
    r = s.post(f'{BASE}/tasks', json={
        'name': name,
        'labels': [{'name': 'object', 'attributes': []}],
        'segment_size': segment_size,
    }, timeout=60)
    r.raise_for_status()
    task_id = r.json()['id']

    files = [('client_files[%d]' % i, (os.path.basename(p), open(p, 'rb'), 'image/png'))
             for i, p in enumerate(images)]
    r = s.post(f'{BASE}/tasks/{task_id}/data', files=files,
               data={'image_quality': '70', 'sorting_method': 'lexicographical'}, timeout=120)
    r.raise_for_status()
    rq_id = r.json().get('rq_id')

    deadline = time.time() + 180
    while time.time() < deadline:
        st = s.get(f'{BASE}/requests/{rq_id}', timeout=30).json()
        if st['status'] in ('finished', 'failed'):
            print(f'  task {task_id} data: {st["status"]} {st.get("message", "")}')
            break
        time.sleep(2)
    return task_id

images = sorted(os.path.join(IMG_DIR, f) for f in os.listdir(IMG_DIR) if f.endswith('.png'))

mixed = make_task('mixed stages', 1, images)
jobs = s.get(f'{BASE}/jobs', params={'task_id': mixed, 'page_size': 50}, timeout=30).json()['results']
jobs.sort(key=lambda j: j['id'])
plan = [
    ('annotation', 'new'),
    ('annotation', 'in progress'),
    ('annotation', 'completed'),
    ('validation', 'in progress'),
    ('acceptance', 'completed'),
    ('validation', 'rejected'),
]
for job, (stage, state) in zip(jobs, plan):
    r = s.patch(f'{BASE}/jobs/{job["id"]}', json={'stage': stage, 'state': state}, timeout=30)
    r.raise_for_status()
    print(f'  job {job["id"]}: {stage}/{state}')

single = make_task('single job', 6, images[:1])
print('tasks:', mixed, single)
