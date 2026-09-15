---
title: Docker Setup
---

# Docker Setup

The fastest way to run InterSystems IRIS locally is with the repository's tested
Docker Compose configuration.

---

## Start IRIS

```bash
docker compose \
  -f examples/docker-compose.yaml \
  up -d --wait --wait-timeout 180
```

This configuration uses `intersystemsdc/iris-community:latest`, waits until IRIS
and its database access are ready, and creates the local development user
`demo` with password `demo`.

Copy the matching example credentials:

```bash
cp .env.example .env
```

Stop the container while preserving or removing its data:

```bash
docker compose -f examples/docker-compose.yaml down
docker compose -f examples/docker-compose.yaml down -v
```

---

## Verify IRIS is running

```bash
# Check container status
docker ps --filter name=iris-haystack

# Check logs
docker logs iris-haystack --tail 30
```

You should see `IRIS for UNIX ... startup successful` in the logs.

---

## Management Portal

Open [http://localhost:52773/csp/sys/UtilHome.csp](http://localhost:52773/csp/sys/UtilHome.csp) in your browser.

Local development credentials:

| Field | Value |
|---|---|
| Username | `demo` |
| Password | `demo` |

### Exploring your data via SQL

Once documents are indexed, you can inspect them directly:

1. Navigate to **System Explorer → SQL**
2. Change the namespace to **USER** (top-left dropdown)
3. Run any SQL query:

```sql
-- List all indexed documents
SELECT id, content, meta FROM SQLUser.HaystackDocuments

-- Count documents
SELECT COUNT(*) FROM SQLUser.HaystackDocuments

-- Self-similarity check (should return 1.0 for each row)
SELECT id, VECTOR_COSINE(embedding, embedding) AS self_sim
FROM SQLUser.HaystackDocuments
WHERE embedding IS NOT NULL
```

---

## Connecting with Python

```python
import iris

conn = iris.connect("localhost:1972/USER", "demo", "demo")
cur = conn.cursor()
cur.execute("SELECT 1")
print(cur.fetchone())  # (1,)
conn.close()
```

If this works, IRIS is ready and `iris-haystack` can connect.

---

## Common issues

### Port already in use

```
Error: Bind for 0.0.0.0:1972 failed: port is already allocated
```

Change the host port in `examples/docker-compose.yaml`:

```yaml
ports:
  - "1973:1972"   # host:container
```

Then update your connection string: `localhost:1973/USER`.

### Container exits immediately

```bash
docker logs iris-haystack
```

This usually means the IRIS data directory has permission issues. Try removing the volume:

```bash
docker compose -f examples/docker-compose.yaml down -v
docker compose -f examples/docker-compose.yaml up -d --wait --wait-timeout 180
```

### Cannot connect from Python

Check that the superserver port is open:

```bash
nc -zv localhost 1972
# Connection to localhost 1972 port [tcp/*] succeeded!
```

If this fails, the container is not running or the port is blocked by a firewall.
