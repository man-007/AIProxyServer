# AI Proxy Server

This project provides a local HTTP proxy for Claude Code and other Anthropic Messages clients. It translates `POST /v1/messages` requests into requests for an OpenAI-compatible upstream provider, such as NVIDIA NIM, and translates the response back to Anthropic format.

The proxy currently supports Anthropic Messages only. `/v1/chat/completions` and `/v1/responses` are upstream paths, not public proxy routes.

## Features

- Anthropic Messages request and response translation
- Streaming SSE support for text and tool calls
- Optional model discovery and local model registry
- Configurable `httpx` or OpenAI SDK upstream transport
- Optional bearer-token authentication for proxy routes
- Optional rate limiting with in-memory or Redis storage
- CORS configuration for browser clients
- Idempotency protection for duplicate requests
- JSON logging and Prometheus metrics
- Runtime configuration through the configuration API

## Requirements

- Python 3.11 or newer
- An HTTPS upstream provider and API key
- Docker and Docker Compose, if using the container deployment

## Installation and local setup

Create a virtual environment and install the development dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Create `.env` in the project root. The application loads this file automatically. Do not commit it or place secrets in source control.

```env
UPSTREAM_BASE_URL=https://integrate.api.nvidia.com
UPSTREAM_API_KEY=replace-with-your-upstream-key
```

Start the server with the included script:

```bash
./start.sh
```

The script uses `.venv/bin/python` when available, sets `PYTHONPATH=src`, and listens on `http://127.0.0.1:8085` by default.

You can also use the Makefile. This uses port 8080 by default:

```bash
make install
make run
```

To choose another host or port:

```bash
make run HOST=127.0.0.1 PORT=8085
```

Or run Uvicorn directly from the project root:

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn proxy_gateway.main:app --host 127.0.0.1 --port 8080
```

The interactive API documentation is available at `/docs`; the OpenAPI document is available at `/openapi.json`.

## Claude Code

For a proxy started by `start.sh` with its default settings:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8085"
export ANTHROPIC_API_KEY="not-used"
```

Use `http://`, not `https://`, for this direct local connection. Put the proxy behind a TLS-terminating reverse proxy when HTTPS is required. An `UNKNOWN_CERTIFICATE_VERIFICATION_ERROR` from Claude Code together with Uvicorn `Invalid HTTP request received` messages usually means an HTTPS client is connecting to this plain-HTTP listener.

## Environment variables

The following variables are read at startup. Values supplied in the process environment take precedence over `.env`.

| Variable                         | Default                            | Purpose                                                                                                                                      |
| -------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `PROXY_HOST`                     | `127.0.0.1`                        | Local bind address. Use `0.0.0.0` in a container. A non-loopback host requires proxy authentication.                                         |
| `PROXY_PORT`                     | `8080`                             | Local listening port. `start.sh` uses `8085` when this variable is unset.                                                                    |
| `UPSTREAM_BASE_URL`              | `https://integrate.api.nvidia.com` | HTTPS host root for the upstream provider. Do not include an API path, query, or fragment.                                                   |
| `UPSTREAM_API_KEY`               | empty                              | API key forwarded to the upstream provider. Required for making the connection between the provide and the server.                           |
| `UPSTREAM_MODELS_PATH`           | `/v1/models`                       | Upstream path used for model discovery.                                                                                                      |
| `UPSTREAM_CHAT_COMPLETIONS_PATH` | `/v1/chat/completions`             | Upstream OpenAI-compatible chat path used after translation. Used by the httpx AsyncClient.                                                  |
| `UPSTREAM_CLIENT`                | `openai`                           | Upstream transport. Valid values are `httpx` and `openai`.                                                                                   |
| `UPSTREAM_TIMEOUT_SECONDS`       | `120`                              | Upstream request timeout in seconds.                                                                                                         |
| `MODEL_DISCOVERY_ENABLED`        | `false`                            | When true, load and validate models through the upstream models endpoint. When false, forward the requested model without startup discovery. |
| `DEFAULT_MODEL`                  | empty                              | Model used when a request does not provide one. Set it to a known registry model when discovery is enabled.                                  |
| `MODEL_CACHE_TTL_SECONDS`        | `300`                              | How long discovered model data remains cached. Set to `0` to disable the cache duration.                                                     |
| `PROXY_AUTH_ENABLED`             | `false`                            | Require a bearer token on the health, model-list, and messages routes.                                                                       |
| `PROXY_API_KEY`                  | empty                              | Token expected by proxy authentication when `PROXY_AUTH_ENABLED=true`.                                                                       |
| `CORS_ALLOWED_ORIGINS`           | localhost ports 3000 and 5173      | Comma-separated browser origins allowed by CORS. Wildcard `*` is rejected.                                                                   |
| `RATE_LIMIT_ENABLED`             | `false`                            | Enable per-client request limiting.                                                                                                          |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `120`                              | Request limit when rate limiting is enabled.                                                                                                 |
| `REDIS_URL`                      | empty                              | Redis connection URL for shared rate-limit state. Empty uses an in-memory store.                                                             |
| `TRUST_PROXY_HEADERS`            | `false`                            | Trust forwarded client-IP headers for rate limiting. Enable only behind a trusted proxy that overwrites them.                                |
| `LOG_LEVEL`                      | `info`                             | Logging verbosity: `DEBUG`, `INFO`, `WARNING`/`WARN`, or `ERROR`.                                                                            |

Example production-oriented settings:

```env
PROXY_HOST=127.0.0.1
PROXY_PORT=8080
UPSTREAM_BASE_URL=https://integrate.api.nvidia.com
UPSTREAM_API_KEY=replace-with-a-long-lived-secret
UPSTREAM_CLIENT=httpx
MODEL_DISCOVERY_ENABLED=true
DEFAULT_MODEL=meta/llama-3.1-70b-instruct
PROXY_AUTH_ENABLED=true
PROXY_API_KEY=replace-with-a-separate-proxy-token
CORS_ALLOWED_ORIGINS=https://app.example.com
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=120
REDIS_URL=redis://redis:6379/0
TRUST_PROXY_HEADERS=true
LOG_LEVEL=info
```

Choosing the right model:

```
curl -s https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_API_KEY" | jq -r '.data[].id' | while read -r m; do
  http=$(curl -sS -o /tmp/resp.txt -w '%{http_code}' --max-time 15 \
    https://integrate.api.nvidia.com/v1/chat/completions \
    -H "Authorization: Bearer $NVIDIA_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8,\"stream\":false}" 2>/dev/null)
  if [ $? -ne 0 ]; then
    echo "$m -> HANG/error"
  else
    echo "$m -> HTTP $http: $(head -c 100 /tmp/resp.txt)"
  fi
done
```

## API endpoints

| Method  | Path            | Description                                                                            |
| ------- | --------------- | -------------------------------------------------------------------------------------- |
| `GET`   | `/`             | Returns a basic service message.                                                       |
| `GET`   | `/health`       | Returns service status, upstream base URL, and loaded model count.                     |
| `GET`   | `/v1/models`    | Returns the local/OpenAI-compatible model list. Refreshes discovery when enabled.      |
| `POST`  | `/v1/messages`  | Accepts an Anthropic Messages request and returns a translated response or SSE stream. |
| `GET`   | `/metrics`      | Returns Prometheus metrics.                                                            |
| `GET`   | `/config`       | Returns the current runtime configuration snapshot.                                    |
| `PATCH` | `/config`       | Updates the supported upstream and logging settings without restarting.                |
| `GET`   | `/docs`         | FastAPI Swagger UI.                                                                    |
| `GET`   | `/openapi.json` | FastAPI OpenAPI document.                                                              |

When proxy authentication is enabled, send this header to protected routes:

```http
Authorization: Bearer <PROXY_API_KEY>
```

The configuration routes currently do not apply the proxy bearer-token dependency. Keep them on a trusted local or private network, or restrict them at the reverse proxy. The configuration response includes the current upstream API key in this customer-managed deployment; protect access accordingly.

Health and model-list examples:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
```

With proxy authentication enabled:

```bash
curl -H "Authorization: Bearer $PROXY_API_KEY" http://127.0.0.1:8080/health
```

## Runtime configuration

`PATCH /config` accepts these JSON fields:

```json
{
  "model_discovery_enabled": true,
  "models_path": "/v1/models",
  "chat_path": "/v1/chat/completions",
  "api_key": "replace-with-a-new-key",
  "request_timeout_seconds": 120,
  "default_model": "meta/llama-3.1-70b-instruct",
  "upstream_client": "httpx",
  "upstream_base_url": "https://integrate.api.nvidia.com",
  "log_level": "info"
}
```

`api_key`, `upstream_api_key`, and `UPSTREAM_API_KEY` are accepted as aliases for the upstream key. Runtime changes affect the current process only; update `.env` as well if they should survive a restart. Invalid values return HTTP 400.

## Duplicate-request protection

The proxy derives an opaque request key from the translated request, or uses the client-provided `Idempotency-Key`. An identical request that is already running receives `409 Conflict` and does not start another upstream generation. Live SSE streams are not replayed. The default coordinator is process-local; use a shared coordinator such as Redis before relying on this protection across multiple replicas.

## Docker

Build and run the image with Docker:

```bash
docker build -t claude-nvidia-proxy .
docker run --rm --env-file .env -p 127.0.0.1:8080:8080 claude-nvidia-proxy
```

The image runs as a non-root user, exposes port `8080`, and starts `proxy_gateway.main:app` directly. Its container health check calls `/health`.

For Compose:

```bash
docker compose up --build -d
docker compose logs -f proxy-gateway
docker compose down
```

Compose reads `.env`, binds the application to `127.0.0.1:8080`, and restarts the service unless stopped. Create `.env` before running Compose; `UPSTREAM_API_KEY` is required.

## Production deployment

Terminate TLS at Nginx, Caddy, Traefik, or another trusted reverse proxy. Keep Uvicorn bound to loopback or an internal container network, and expose only HTTPS publicly. Set `PROXY_AUTH_ENABLED=true` with a long random `PROXY_API_KEY`; TLS does not replace application authentication.

Example Nginx location:

```nginx
server {
    listen 443 ssl;
    server_name proxy.example.com;

    ssl_certificate /etc/letsencrypt/live/proxy.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/proxy.example.com/privkey.pem;
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 600s;
    }
}
```

For a public deployment:

- Use exact HTTPS values in `CORS_ALLOWED_ORIGINS`; do not use `*`.
- Restrict `/config` at the edge because it can change upstream behavior and expose the configured upstream key.
- Enable rate limiting. Use `REDIS_URL` when multiple workers or replicas must share limits.
- Set `TRUST_PROXY_HEADERS=true` only when the reverse proxy overwrites forwarding headers.
- Keep the upstream URL HTTPS and rotate both upstream and proxy credentials regularly.
- Restrict or remove public access to `/health`, `/v1/models`, and `/metrics` when they are not needed.

## Logging

Normal operation is logged at `INFO`; cache hits, request timing, model resolution, and upstream connection details are logged at `DEBUG`; rejected requests and degraded fallback are `WARNING`; failed upstream calls and unhandled exceptions are `ERROR`. Request bodies, tool arguments, API keys, and stream chunks are intentionally not logged.

## Tests

Run the test suite with:

```bash
make test
```

Or:

```bash
.venv/bin/python -m pytest -q
```
