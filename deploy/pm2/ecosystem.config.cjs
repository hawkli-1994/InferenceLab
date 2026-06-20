const path = require("node:path");

const repoRoot = path.resolve(__dirname, "../..");
const frontendRoot = path.join(repoRoot, "frontend");
const localDb = path.join(repoRoot, "backend", "inflab-dev.db");

const apiHost = process.env.INFLAB_API_HOST || "127.0.0.1";
const apiPort = process.env.INFLAB_API_PORT || "8000";
const uiHost = process.env.INFLAB_UI_HOST || "127.0.0.1";
const uiPort = process.env.INFLAB_UI_PORT || "5173";
const redisUrl = process.env.INFLAB_REDIS_URL || "redis://127.0.0.1:6379/0";
const queueName = process.env.INFLAB_REDIS_QUEUE_NAME || "default";

const localApiEnv = {
  PYTHONUNBUFFERED: "1",
  INFLAB_ENVIRONMENT: process.env.INFLAB_ENVIRONMENT || "pm2-local",
  INFLAB_LOG_LEVEL: process.env.INFLAB_LOG_LEVEL || "INFO",
  INFLAB_SECRET_KEY: process.env.INFLAB_SECRET_KEY || "inference-lab-pm2-dev-key",
  INFLAB_DATABASE_URL:
    process.env.INFLAB_DATABASE_URL || `sqlite+pysqlite:///${localDb}`,
  INFLAB_DATABASE_CREATE_SCHEMA_ON_STARTUP:
    process.env.INFLAB_DATABASE_CREATE_SCHEMA_ON_STARTUP || "true",
  INFLAB_SEED_DEMO_DATA: process.env.INFLAB_SEED_DEMO_DATA || "true",
  INFLAB_REDIS_URL: redisUrl,
  INFLAB_REDIS_QUEUE_NAME: queueName,
  INFLAB_REDIS_JOB_MODE: process.env.INFLAB_REDIS_JOB_MODE || "sync",
  INFLAB_LLM_PROVIDER: process.env.INFLAB_LLM_PROVIDER || "disabled",
  INFLAB_AGENT_EXECUTOR_PROVIDER:
    process.env.INFLAB_AGENT_EXECUTOR_PROVIDER || "pi"
};

module.exports = {
  apps: [
    {
      name: "inflab-api",
      cwd: repoRoot,
      script: "uv",
      args: [
        "run",
        "uvicorn",
        "inflab.api.app:app",
        "--host",
        apiHost,
        "--port",
        apiPort,
        "--reload"
      ],
      exec_interpreter: "none",
      exec_mode: "fork",
      env: localApiEnv,
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "5s"
    },
    {
      name: "inflab-frontend",
      cwd: frontendRoot,
      script: "pnpm",
      args: ["dev", "--host", uiHost, "--port", uiPort],
      exec_interpreter: "none",
      exec_mode: "fork",
      env: {
        NODE_ENV: process.env.NODE_ENV || "development",
        VITE_API_BASE:
          process.env.VITE_API_BASE || `http://${apiHost}:${apiPort}/api/v1`
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "5s"
    },
    {
      name: "inflab-worker",
      cwd: repoRoot,
      script: "uv",
      args: ["run", "rq", "worker", "--url", redisUrl, queueName],
      exec_interpreter: "none",
      exec_mode: "fork",
      env: {
        ...localApiEnv,
        INFLAB_REDIS_JOB_MODE: "rq"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "5s"
    }
  ]
};
